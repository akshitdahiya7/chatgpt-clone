import uuid
from pathlib import Path

from app.document.chunkers.factory import ChunkerFactory
from app.document.factory import DocumentFactory
from app.embeddings.service import EmbeddingService
from app.settings import get_settings
from app.vectordb.models import VectorDocument
from app.vectordb.service import VectorStoreService

settings = get_settings()


class IngestionService:

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()

    def ingest(
        self,
        file_path: Path,
        user_id: str = "demo-user",
        document_id: str | None = None,
    ) -> int:

        # Generate document ID if not provided
        if document_id is None:
            document_id = uuid.uuid4().hex

        # Read document
        reader = DocumentFactory.get_reader(file_path)
        pages = reader.read(file_path)

        # Chunk document
        chunker = ChunkerFactory.get(
            strategy=settings.rag_chunk_strategy
        )

        chunks = chunker.split(pages)

        if not chunks:
            return 0

        # One request per batch of chunks, not one request per chunk.
        embeddings = self.embedding_service.embed_batch(
            [chunk.text for chunk in chunks]
        )

        documents = [
            VectorDocument(
                id=f"{document_id}_{chunk.index}",
                user_id=user_id,
                document_id=document_id,
                chunk_index=chunk.index,
                page=chunk.page,
                content=chunk.text,
                embedding=embedding,
            )
            # strict=True so a length mismatch raises instead of silently
            # dropping chunks.
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

        self.vector_store.upsert(documents)

        return len(documents)