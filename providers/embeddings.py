import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class EmbeddingConfig(BaseModel):
    """Configuration for local embeddings."""
    model_name: str = "all-MiniLM-L6-v2"
    device: str = "cpu"
    enabled: bool = True

class EmbeddingProvider:
    """Provides local text embeddings using sentence-transformers."""

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self.config = config or EmbeddingConfig()
        self._model: Any | None = None

    def _load_model(self) -> Any | None:
        if not self.config.enabled:
            return None

        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.config.model_name}")
                self._model = SentenceTransformer(
                    self.config.model_name,
                    device=self.config.device
                )
            except ImportError:
                logger.warning("sentence-transformers not installed. Embeddings disabled.")
                self.config.enabled = False
                return None
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                self.config.enabled = False
                return None

        return self._model

    def embed(self, text: str) -> list[float]:
        """Generates embeddings for a single string."""
        model = self._load_model()
        if model is None:
            return []

        try:
            # Output is a numpy array
            import typing
            result = model.encode(text)
            return typing.cast(list[float], result.tolist())
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a batch of strings."""
        if not texts:
            return []

        model = self._load_model()
        if model is None:
            return [[] for _ in texts]

        try:
            results = model.encode(texts)
            return [r.tolist() for r in results]
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return [[] for _ in texts]
