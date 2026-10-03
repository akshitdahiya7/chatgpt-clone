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
    ) -> list[RetrievedChunk]:
        """Return the nearest chunks for the query embedding."""
        raise NotImplementedError
