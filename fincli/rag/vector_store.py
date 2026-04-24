"""
AI ENGINEERING CONCEPT — Vector Store & Similarity Search:

A vector store lets you ask: "which stored vectors are most similar to this query vector?"

COSINE SIMILARITY — the standard metric:
  similarity = dot(A, B) / (|A| × |B|)
  Range: -1 to 1
    1.0  = identical direction (same meaning)
    0.0  = orthogonal (unrelated)
   -1.0  = opposite meaning

WHY cosine over euclidean distance?
  Euclidean measures absolute distance. Cosine measures the ANGLE between vectors.
  Angle is more robust — it ignores the magnitude (length) of the vector,
  which can vary based on text length. Industry default is cosine.

HOW we store vectors:
  numpy float32 array → .tobytes() → SQLite BLOB
  On retrieval: np.frombuffer(bytes, dtype=np.float32) → back to array

SCALING NOTE (what AI engineers know):
  - Up to ~100K vectors: in-memory numpy is fine (what we're doing)
  - 100K–10M vectors: use FAISS (Meta's library) or sqlite-vec
  - 10M+ vectors: dedicated vector DB (Pinecone, Weaviate, Qdrant)
  At your transaction volume (hundreds to low thousands), numpy is the right choice.
"""
import numpy as np
from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from fincli.storage.models import TransactionEmbedding
from fincli.utils.logger import get_logger

logger = get_logger(__name__)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    # 1e-10 prevents division by zero for zero vectors
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


class VectorStore:
    def __init__(self, session: Session):
        self.session = session

    def upsert(
        self,
        transaction_id: int,
        embedding_bytes: bytes,
        embedding_text: str,
        model: str,
    ) -> None:
        existing = self.session.execute(
            select(TransactionEmbedding).where(
                TransactionEmbedding.transaction_id == transaction_id
            )
        ).scalar_one_or_none()

        if existing:
            existing.embedding = embedding_bytes
            existing.embedding_text = embedding_text
            existing.model = model
        else:
            self.session.add(
                TransactionEmbedding(
                    transaction_id=transaction_id,
                    embedding=embedding_bytes,
                    embedding_text=embedding_text,
                    model=model,
                )
            )

    def search(
        self,
        query_vector: np.ndarray,
        candidate_ids: List[int],
        top_k: int = 8,
    ) -> List[Tuple[int, float]]:
        """
        Compute cosine similarity between query_vector and all candidate embeddings.
        Returns top_k (transaction_id, score) pairs sorted by similarity descending.

        We load only the candidates (pre-filtered by SQL), not the full table.
        This is the hybrid retrieval pattern: SQL narrows the set, vectors rank it.
        """
        if not candidate_ids:
            return []

        rows = self.session.execute(
            select(TransactionEmbedding).where(
                TransactionEmbedding.transaction_id.in_(candidate_ids)
            )
        ).scalars().all()

        scored = []
        for row in rows:
            vec = np.frombuffer(row.embedding, dtype=np.float32)
            score = cosine_similarity(query_vector, vec)
            scored.append((row.transaction_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def get_unindexed_ids(self, all_transaction_ids: List[int]) -> List[int]:
        """Return IDs that have no embedding yet."""
        indexed = {
            row
            for row in self.session.execute(
                select(TransactionEmbedding.transaction_id)
            ).scalars().all()
        }
        return [tid for tid in all_transaction_ids if tid not in indexed]
