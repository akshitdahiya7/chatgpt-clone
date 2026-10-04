from app.settings import get_settings
from app.vectordb.service import VectorStoreService


class RetrieverService:

    def __init__(self):
        self.vector_store_service = VectorStoreService()
        self.min_score = get_settings().rag_min_score

    def retrieve(
        self,
        query: str,
        embedding: list[float],
        top_k: int,
        user_id: str,
        document_ids: list[str] | None = None,
    ):
        chunks = self.vector_store_service.search(
            query,
            embedding,
            top_k,
            user_id,
            document_ids,
        )

        # Weak matches are worse than no matches: they push the model towards
        # answering from unrelated text instead of saying it does not know.
        return [
            chunk for chunk in chunks
            if chunk.score >= self.min_score
        ]
