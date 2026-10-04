import hashlib
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
    ) -> str:

        # Read document
        reader = DocumentFactory.get_reader(file_path)
        pages = reader.read(file_path)

        text = "".join(page.text for page in pages)

        # A scanned PDF has pages but no text layer. Without this the upload
        # succeeds, indexes nothing, and the user never finds out.
        if not text.strip():
            raise ValueError(
                "No readable text found. This looks like a scanned image, "
                "which needs OCR before it can be indexed."
            )

        # Derive the id from the content, so re-uploading the same file
        # overwrites its chunks instead of adding a duplicate copy.
        if document_id is None:
            document_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

        # Chunk document
        chunker = ChunkerFactory.get(
            strategy=settings.rag_chunk_strategy
        )

        chunks = chunker.split(pages)

        if not chunks:
            return document_id

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
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

        self.vector_store.upsert(documents)

        print(f"INGESTED {len(documents)} chunks as {document_id}")

        return document_id
