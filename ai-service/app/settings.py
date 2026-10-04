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
    vector_store_provider: str = "opensearch"
    vector_index_name: str = "documents"

    # Drop chunks below this score so unrelated text never reaches the model.
    # Measured on this data: questions the documents can answer score 0.59-0.71,
    # questions they cannot score 0.49-0.55. Retune if you change the embedding
    # model or the kind of documents.
    rag_min_score: float = 0.58

    # Must match what the embedding provider returns, and cannot change once
    # the index exists. text-embedding-3-small=1536, all-MiniLM-L6-v2=384.
    embedding_dimension: int = 1536

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
