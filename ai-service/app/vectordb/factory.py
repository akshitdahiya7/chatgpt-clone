from app.settings import get_settings


class VectorStoreFactory:

    @staticmethod
    def get_provider():
        settings = get_settings()

        if settings.vector_store_provider != "opensearch":
            raise ValueError(
                f"Unsupported vector store provider: {settings.vector_store_provider}"
            )

        # Without all three, requests reach OpenSearch unauthenticated and come
        # back as a confusing "User: anonymous" authorization error.
        if not (
            settings.opensearch_host
            and settings.opensearch_user
            and settings.opensearch_password
        ):
            raise ValueError(
                "OPENSEARCH_HOST, OPENSEARCH_USER and OPENSEARCH_PASSWORD are required"
            )

        from app.vectordb.providers import OpenSearchVectorStore

        return OpenSearchVectorStore(
            host=settings.opensearch_host,
            user=settings.opensearch_user,
            password=settings.opensearch_password,
            index_name=settings.vector_index_name,
        )
