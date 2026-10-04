from app.document.service import IngestionService
from app.embeddings.service import EmbeddingService
from app.llm.models import LLMResponse
from app.llm.service import LLMService
from app.prompt.service import PromptService
from app.retriever.service import RetrieverService


class RAGService:

    def __init__(self):
        self.ingestion_service = IngestionService()
        self.embedding_service = EmbeddingService()
        self.retriever_service = RetrieverService()
        self.prompt_service = PromptService()
        self.llm_service = LLMService()

    def _context(
        self,
        question: str,
        top_k: int,
        user_id: str,
        document_ids: list[str] | None = None,
    ):
        """Embed the question and build a prompt from the retrieved chunks."""

        embedding = self.embedding_service.embed(question)

        chunks = self.retriever_service.retrieve(
            query=question,
            embedding=embedding,
            top_k=top_k,
            user_id=user_id,
            document_ids=document_ids,
        )

        return self.prompt_service.rag(
            question=question,
            context=chunks,
        )

    def chat(
        self,
        question: str,
        model: str,
        top_k: int,
        temperature: float,
        max_tokens: int,
        top_p: float,
        user_id: str = "demo-user",
        document_ids: list[str] | None = None,
    ) -> LLMResponse:
        """Answer in one response."""

        return self.llm_service.generate(
            prompt=self._context(question, top_k, user_id, document_ids),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

    def chat_stream(
        self,
        question: str,
        model: str,
        top_k: int,
        temperature: float,
        max_tokens: int,
        top_p: float,
        user_id: str = "demo-user",
        document_ids: list[str] | None = None,
    ):
        """Answer as a stream of text pieces."""

        yield from self.llm_service.stream(
            prompt=self._context(question, top_k, user_id, document_ids),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
