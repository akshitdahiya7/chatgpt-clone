from opensearchpy import OpenSearch, RequestsHttpConnection, helpers

from app.settings import get_settings
from app.vectordb.models import RetrievedChunk, VectorDocument
from app.vectordb.providers.base import BaseVectorStore


class OpenSearchVectorStore(BaseVectorStore):

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        index_name: str,
    ):
        settings = get_settings()

        self.index_name = index_name
        self.embedding_dimension = settings.embedding_dimension

        # host must be a bare hostname: the console shows it with an https:// prefix.
        host = host.replace("https://", "").replace("http://", "").rstrip("/")

        self.client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=(user, password),
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30,
        )

    def create_index(self, recreate: bool = False) -> None:

        if self.client.indices.exists(index=self.index_name):

            if recreate:
                print(f"Deleting '{self.index_name}'...")
                self.client.indices.delete(index=self.index_name)
            else:
                print(f"Index '{self.index_name}' already exists.")
                return

        body = {

            # knn must be enabled at the index level or knn_vector is rejected.
            "settings": {
                "index": {
                    "knn": True,
                }
            },

            "mappings": {
                "properties": {

                    # keyword, not text: these are filtered on exactly, never analysed.
                    "user_id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},

                    "chunk_index": {"type": "integer"},
                    "page": {"type": "integer"},

                    "content": {"type": "text"},

                    "embedding": {
                        "type": "knn_vector",
                        "dimension": self.embedding_dimension,
                        "method": {
                            "name": "hnsw",
                            # cosinesimil matches the normalised embeddings the
                            # providers emit; use l2 only if normalisation stops.
                            "space_type": "cosinesimil",
                            # lucene supports filtered k-NN queries.
                            "engine": "lucene",
                        },
                    },

                }
            },

        }

        self.client.indices.create(index=self.index_name, body=body)

        print(f"Created index '{self.index_name}' successfully.")

    def upsert(self, docs: list[VectorDocument]) -> None:

        # Create the index first if it is missing. Otherwise OpenSearch creates
        # it automatically with a dynamic mapping, where `embedding` becomes a
        # plain float array instead of knn_vector, and every search then fails
        # with "Field 'embedding' is not knn_vector type."
        if not self.client.indices.exists(index=self.index_name):
            self.create_index()

        actions = [
            {
                "_index": self.index_name,
                "_id": doc.id,
                "_source": doc.to_dict(),
            }
            for doc in docs
        ]

        success, errors = helpers.bulk(
            self.client,
            actions,
            refresh=True,  # make the docs searchable immediately
        )

        print(f"Indexed {success} document(s).")

        if errors:
            print(f"Errors: {errors}")

    def search(
        self,
        query: str,
        embedding: list[float],
        k: int,
        user_id: str,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:

        # Always scope to the user. Narrow to specific documents when the
        # caller asks, which is what happens when files came with the question.
        filters = [{"term": {"user_id": user_id}}]

        if document_ids:
            filters.append({"terms": {"document_id": document_ids}})

        body = {
            "size": k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": embedding,
                        "k": k,
                        "filter": {"bool": {"must": filters}},
                    }
                }
            },
            "_source": [
                "id",
                "user_id",
                "document_id",
                "chunk_index",
                "page",
                "content",
            ],
        }

        response = self.client.search(index=self.index_name, body=body)

        return [
            RetrievedChunk(
                content=hit["_source"]["content"],
                page=hit["_source"]["page"],
                document_id=hit["_source"]["document_id"],
                # cosinesimil scores land in [0, 1], higher is closer
                score=hit["_score"],
            )
            for hit in response["hits"]["hits"]
        ]
