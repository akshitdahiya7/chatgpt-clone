from app.settings import get_settings


class VectorStoreFactory:

    @staticmethod
    def get_provider():
        settings = get_settings()

        match settings.vector_store_provider:
            case "qdrant":
                from app.vectordb.providers import QdrantVectorStore

                if not settings.qdrant_url:
                    raise ValueError("QDRANT_URL is required")

                return QdrantVectorStore(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key,
                    index_name=settings.vector_index_name,
                )

            case "opensearch":
                from app.vectordb.providers import OpenSearchVectorStore

                if not (
                    settings.opensearch_host
                    and settings.opensearch_user
                    and settings.opensearch_password
                ):
                    raise ValueError(
                        "OPENSEARCH_HOST, OPENSEARCH_USER and "
                        "OPENSEARCH_PASSWORD are required"
                    )

                return OpenSearchVectorStore(
                    host=settings.opensearch_host,
                    user=settings.opensearch_user,
                    password=settings.opensearch_password,
                    index_name=settings.vector_index_name,
                )

            case _:
                raise ValueError(
                    "Unsupported vector store provider: "
                    f"{settings.vector_store_provider}"
                )
