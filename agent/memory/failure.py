import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from providers.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

class FailureRecord(BaseModel):
    """Represents a failed attempt to learn from it later."""
    error_signature: str
    goal: str
    hypothesis: str
    result: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FailureMemory:
    """Uses ChromaDB and vector embeddings to search past failures."""

    def __init__(
        self,
        db_path: str = "memory/failures",
        provider: EmbeddingProvider | None = None
    ) -> None:
        self.db_path = Path(db_path)
        self.provider = provider or EmbeddingProvider()
        self.client: Any | None = None
        self.collection: Any | None = None
        self.enabled = True

        self._init_chroma()

    def _init_chroma(self) -> None:
        try:
            import chromadb
            from chromadb.config import Settings

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(anonymized_telemetry=False)
            )

            # Using cosine similarity for text embeddings
            self.collection = self.client.get_or_create_collection(
                name="agent_failures",
                metadata={"hnsw:space": "cosine"}
            )
        except ImportError:
            logger.warning("chromadb not installed. FailureMemory disabled.")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.enabled = False

    def record_failure(self, record: FailureRecord) -> None:
        """Embeds and saves the failure record."""
        if not self.enabled or self.collection is None:
            return

        embedding = self.provider.embed(record.error_signature)
        if not embedding:
            # Fallback to no embedding if provider fails
            return

        # ChromaDB requires string IDs
        doc_id = f"fail_{int(record.timestamp.timestamp())}_{hash(record.error_signature)}"

        metadata = {
            "error_signature": record.error_signature,
            "goal": record.goal,
            "hypothesis": record.hypothesis,
            "result": record.result,
            "timestamp": record.timestamp.isoformat()
        }

        try:
            self.collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[record.error_signature],
                metadatas=[metadata]
            )
        except Exception as e:
            logger.error(f"Failed to save failure record to Chroma: {e}")

    def search_similar_errors(
        self, error_signature: str, limit: int = 5, distance_threshold: float = 0.3
    ) -> list[FailureRecord]:
        """Searches for similar past errors based on semantic similarity."""
        if not self.enabled or self.collection is None:
            return []

        embedding = self.provider.embed(error_signature)
        if not embedding:
            return []

        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit
            )

            records = []
            if not results["metadatas"] or not results["distances"]:
                return []

            for metadata, distance in zip(
                results["metadatas"][0], results["distances"][0], strict=False
            ):
                # Distances in Chroma with cosine space: 0 is exact match, 1 is orthogonal
                if distance > distance_threshold:
                    continue

                records.append(FailureRecord(
                    error_signature=metadata["error_signature"],
                    goal=metadata["goal"],
                    hypothesis=metadata["hypothesis"],
                    result=metadata["result"],
                    timestamp=datetime.fromisoformat(metadata["timestamp"])
                ))

            return records
        except Exception as e:
            logger.error(f"Failed to search similar errors in Chroma: {e}")
            return []
