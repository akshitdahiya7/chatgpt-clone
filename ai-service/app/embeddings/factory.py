from app.settings import get_settings


class EmbeddingFactory:

    @staticmethod
    def get_provider():
        settings = get_settings()

        match settings.embedding_provider:
            case "openai":
                from app.embeddings.providers.openai_embeddings import (
                    OpenAIEmbeddingProvider,
                )

                if not settings.openai_api_key:
                    raise ValueError("OPENAI_API_KEY is required")

                return OpenAIEmbeddingProvider(
                    api_key=settings.openai_api_key,
                    model=settings.embedding_model,
                    dimensions=settings.embedding_dimension,
                    batch_size=settings.embedding_batch_size,
                    base_url=settings.openai_base_url,
                )

            case "huggingface":
                from app.embeddings.providers.huggingface import HuggingFaceProvider

                return HuggingFaceProvider(model_name=settings.embedding_model)

            case _:
                raise ValueError(
                    f"Unsupported embedding provider: {settings.embedding_provider}"
                )
