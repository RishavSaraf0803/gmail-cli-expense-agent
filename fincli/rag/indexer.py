"""
AI ENGINEERING CONCEPT — Indexing (Offline vs Online):

Indexing is ALWAYS offline (separate from query time). This is a core principle.

WHY separate?
  - Embedding is slow: ~50-200ms per transaction
  - Chat must feel instant: retrieval should be <500ms total
  - If you embedded at query time, a user with 1000 transactions would wait
    1000 × 150ms = 2.5 minutes before getting an answer

Industry pattern:
  [fetch emails] → [save transactions] → [index: embed + store] (background/CLI)
  [user asks question] → [retrieve from pre-built index] → [LLM answers]

This is identical to how Google Search works: crawl + index offline, serve fast.

INCREMENTAL vs FULL REINDEX:
  - index_new(): only processes transactions without embeddings (fast, idempotent)
  - reindex_all(): re-embeds everything (use when you change the embedding model
    or the text format in to_embedding_text())

AI ENGINEERS WATCH FOR:
  - Index drift: transactions added but not indexed → stale search results
  - Model mismatch: embedding table has vectors from different models mixed together
    (always store model name alongside the vector)
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from fincli.storage.models import Transaction
from fincli.rag.embedder import OllamaEmbedder
from fincli.rag.vector_store import VectorStore
from fincli.utils.logger import get_logger

logger = get_logger(__name__)


class TransactionIndexer:
    def __init__(self, session: Session, embedder: OllamaEmbedder):
        self.session = session
        self.embedder = embedder
        self.vector_store = VectorStore(session)

    def index_new(self) -> int:
        """
        Embed transactions that don't have embeddings yet.
        Idempotent — safe to run multiple times.
        Returns number of transactions indexed.
        """
        all_ids = list(
            self.session.execute(select(Transaction.id)).scalars().all()
        )
        unindexed = self.vector_store.get_unindexed_ids(all_ids)

        if not unindexed:
            logger.info("rag_index_nothing_new")
            return 0

        logger.info("rag_index_start", count=len(unindexed))

        transactions = list(
            self.session.execute(
                select(Transaction).where(Transaction.id.in_(unindexed))
            ).scalars().all()
        )

        indexed = 0
        failed = 0
        for txn in transactions:
            try:
                text = txn.to_embedding_text()
                embedding_bytes = self.embedder.embed_to_bytes(text)
                self.vector_store.upsert(
                    transaction_id=txn.id,
                    embedding_bytes=embedding_bytes,
                    embedding_text=text,
                    model=self.embedder.model,
                )
                indexed += 1
            except Exception as e:
                failed += 1
                logger.error("rag_index_transaction_failed", transaction_id=txn.id, error=str(e))

        self.session.commit()
        logger.info("rag_index_complete", indexed=indexed, failed=failed)
        return indexed

    def reindex_all(self) -> int:
        """
        Re-embed ALL transactions. Use after changing embedding model or text format.
        This is expensive — runs proportional to total transaction count.
        """
        transactions = list(
            self.session.execute(select(Transaction)).scalars().all()
        )
        logger.info("rag_reindex_start", total=len(transactions))

        indexed = 0
        for txn in transactions:
            try:
                text = txn.to_embedding_text()
                embedding_bytes = self.embedder.embed_to_bytes(text)
                self.vector_store.upsert(
                    transaction_id=txn.id,
                    embedding_bytes=embedding_bytes,
                    embedding_text=text,
                    model=self.embedder.model,
                )
                indexed += 1
            except Exception as e:
                logger.error("rag_reindex_transaction_failed", transaction_id=txn.id, error=str(e))

        self.session.commit()
        logger.info("rag_reindex_complete", indexed=indexed)
        return indexed
