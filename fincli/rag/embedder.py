"""
AI ENGINEERING CONCEPT — Embeddings:

An embedding model converts text into a fixed-size list of floats called a vector.
Example: "paid ₹450 at Swiggy" → [0.12, -0.34, 0.89, ... ] (768 numbers)

WHY this works: the model is trained so that semantically similar text lands
"close together" in this 768-dimensional space. "Swiggy food order" and
"Zomato dinner delivery" will have similar vectors even though they share no words.

This is fundamentally different from keyword search (which needs exact word matches).

KEY NUMBERS AI engineers know:
- nomic-embed-text: 768 dims, free via Ollama, great for English
- OpenAI text-embedding-3-small: 1536 dims, $0.00002/1K tokens
- OpenAI text-embedding-3-large: 3072 dims, higher quality
- Dimensions ≠ quality — a well-trained small model beats a bad large one

GOTCHA: vectors from different embedding models are INCOMPATIBLE.
If you switch models, you must re-embed everything (that's what reindex_all does).
"""
import numpy as np
import requests
from typing import Optional

from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmbedderError(Exception):
    pass


class OllamaEmbedder:
    """Calls Ollama's /api/embeddings endpoint to get text vectors."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_embed_model

    def embed(self, text: str) -> np.ndarray:
        """
        Convert text to a float32 numpy vector.

        The vector has no human-readable meaning — it's a point in high-dimensional
        space where proximity = semantic similarity.
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=30,
            )
            response.raise_for_status()
            vector = response.json()["embedding"]
            return np.array(vector, dtype=np.float32)
        except requests.RequestException as e:
            logger.error("embedder_request_failed", error=str(e), model=self.model)
            raise EmbedderError(f"Ollama embedding failed: {e}")

    def embed_to_bytes(self, text: str) -> bytes:
        """Serialize vector to bytes for SQLite BLOB storage."""
        return self.embed(text).tobytes()

    @staticmethod
    def bytes_to_vector(data: bytes) -> np.ndarray:
        """Deserialize bytes back to numpy vector."""
        return np.frombuffer(data, dtype=np.float32)

    def health_check(self) -> bool:
        try:
            # A cheap embed call to verify the model is loaded
            self.embed("test")
            return True
        except EmbedderError:
            return False
