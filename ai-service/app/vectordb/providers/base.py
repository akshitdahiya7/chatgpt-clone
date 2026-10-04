from abc import ABC, abstractmethod

from app.vectordb.models import RetrievedChunk, VectorDocument


class BaseVectorStore(ABC):

    @abstractmethod
    def create_index(self, recreate: bool = False) -> None:
        """Create the vector index, optionally deleting an existing one first."""
        raise NotImplementedError

    @abstractmethod
    def upsert(self, docs: list[VectorDocument]) -> None:
        """Insert or update vector documents."""
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        embedding: list[float],
        k: int,
        user_id: str,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Return the nearest chunks for this user, optionally limited to
        specific documents."""
        raise NotImplementedError
