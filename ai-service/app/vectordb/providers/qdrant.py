import uuid

from qdrant_client import QdrantClient, models

from app.settings import get_settings
from app.vectordb.models import RetrievedChunk, VectorDocument
from app.vectordb.providers.base import BaseVectorStore

# Qdrant point ids must be UUIDs or unsigned integers, but our chunk ids look
# like "<hash>_<index>". Hashing them into a fixed namespace keeps the id
# stable, so re-uploading a file still overwrites its chunks.
NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")


class QdrantVectorStore(BaseVectorStore):

    def __init__(
        self,
        url: str,
        api_key: str,
        index_name: str,
    ):
        settings = get_settings()

        self.index_name = index_name
        self.embedding_dimension = settings.embedding_dimension

        self.client = QdrantClient(
            url=url,
            api_key=api_key or None,
            timeout=30,
        )

    def create_index(self, recreate: bool = False) -> None:

        if self.client.collection_exists(self.index_name):

            if recreate:
                print(f"Deleting '{self.index_name}'...")
                self.client.delete_collection(self.index_name)
            else:
                print(f"Index '{self.index_name}' already exists.")
                return

        self.client.create_collection(
            collection_name=self.index_name,
            vectors_config=models.VectorParams(
                size=self.embedding_dimension,
                distance=models.Distance.COSINE,
            ),
        )

        # Payload indexes make the user and document filters fast.
        for field in ("user_id", "document_id"):
            self.client.create_payload_index(
                collection_name=self.index_name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

        print(f"Created index '{self.index_name}' successfully.")

    def upsert(self, docs: list[VectorDocument]) -> None:

        if not self.client.collection_exists(self.index_name):
            self.create_index()

        points = [
            models.PointStruct(
                id=str(uuid.uuid5(NAMESPACE, doc.id)),
                vector=doc.embedding,
                payload={
                    "user_id": doc.user_id,
                    "document_id": doc.document_id,
                    "chunk_index": doc.chunk_index,
                    "page": doc.page,
                    "content": doc.content,
                },
            )
            for doc in docs
        ]

        self.client.upsert(
            collection_name=self.index_name,
            points=points,
            wait=True,  # make them searchable immediately
        )

        print(f"Indexed {len(points)} document(s).")

    def search(
        self,
        query: str,
        embedding: list[float],
        k: int,
        user_id: str,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:

        conditions = [
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=user_id),
            )
        ]

        if document_ids:
            conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=document_ids),
                )
            )

        results = self.client.query_points(
            collection_name=self.index_name,
            query=embedding,
            limit=k,
            query_filter=models.Filter(must=conditions),
            with_payload=True,
        ).points

        return [
            RetrievedChunk(
                content=point.payload["content"],
                page=point.payload["page"],
                document_id=point.payload["document_id"],
                # Qdrant returns raw cosine similarity in [-1, 1], while
                # OpenSearch returns (1 + cosine) / 2. Rescale so one
                # rag_min_score works for both.
                score=(point.score + 1) / 2,
            )
            for point in results
        ]
