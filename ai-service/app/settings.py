from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: str = "AI Service"
    version: str = "0.1.0"

    env: str = "DEV"
    port: int = 8002

    # Chunking
    rag_chunk_strategy: str = "recursive"  # "recursive" | "fixed"
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200

    # Embeddings: "openai" calls the API, "huggingface" runs locally
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_batch_size: int = 128

    # Vector store
    vector_store_provider: str = "qdrant"  # "qdrant" | "opensearch"
    vector_index_name: str = "documents"

    # Both providers report (1 + cosine) / 2, so 0.5 is cosine 0: drop only
    # chunks pointing away from the question. Relevance is then judged by the
    # model, which is told to answer solely from the context and does refuse
    # when the context does not contain the answer.
    #
    # A higher floor looks tempting but blocks real questions: "what is this
    # document about" scores 0.62 and "what does it say" 0.57, because a
    # question about a document shares little vocabulary with its contents.
    rag_min_score: float = 0.50

    # Must match what the embedding provider returns, and cannot change once
    # the index exists. text-embedding-3-small=1536, all-MiniLM-L6-v2=384.
    embedding_dimension: int = 1536

    # Qdrant Cloud: full URL including https://
    qdrant_url: str = ""
    qdrant_api_key: str = ""

    # OpenSearch: host only, without the https:// prefix
    opensearch_host: str = ""
    opensearch_user: str = ""
    opensearch_password: str = ""

    # LLM: "openai" or "ollama"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.2
    llm_top_p: float = 1.0

    # Shared by the OpenAI embedding and LLM providers.
    # Leave base_url empty for OpenAI itself.
    openai_api_key: str = ""
    openai_base_url: str = ""

    # Only for llm_provider="ollama"
    ollama_base_url: str = ""
    ollama_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
