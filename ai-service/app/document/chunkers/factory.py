from app.document.chunkers.fixed import FixedChunker
from app.document.chunkers.recursive import RecursiveChunker
from app.settings import get_settings


class ChunkerFactory:

    @staticmethod
    def get(strategy: str):
        settings = get_settings()

        match strategy:
            case "recursive":
                chunker = RecursiveChunker
            case "fixed":
                chunker = FixedChunker
            case _:
                raise ValueError(f"Unknown chunking strategy: {strategy}")

        return chunker(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
