from abc import ABC, abstractmethod

from app.document.models import DocumentPage

from .models import Chunk


class Chunker(ABC):

    @abstractmethod
    def split(self, pages: list[DocumentPage]) -> list[Chunk]:
        pass
