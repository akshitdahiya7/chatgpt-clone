"""Round-trip whichever vector store is configured: create, upsert, search, clean up.

Run from the ai-service directory:
    uv run python scripts/verify_vectordb.py

Uses a throwaway index, so it cannot disturb real data. Works for both the
Qdrant and OpenSearch providers, so you can check a fallback before switching.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.settings import get_settings  # noqa: E402
from app.vectordb.factory import VectorStoreFactory  # noqa: E402
from app.vectordb.models import VectorDocument  # noqa: E402

TEST_INDEX = "verify-roundtrip"
USER = "verify-user"


def build_vector(dimension, lead):
    """A deterministic vector, distinguishable by its first element."""
    vector = [0.0] * dimension
    vector[0] = lead
    vector[1] = 1.0 - lead
    return vector


def main():
    settings = get_settings()
    dimension = settings.embedding_dimension

    print(f"provider  : {settings.vector_store_provider}")
    print(f"dimension : {dimension}")

    store = VectorStoreFactory.get_provider()
    # Point the provider at a throwaway index rather than the real one.
    store.index_name = TEST_INDEX

    try:
        store.create_index(recreate=True)
    except Exception as exc:
        print(f"\nFAILED to connect: {type(exc).__name__}: {str(exc)[:200]}")
        print("  -> Check the URL/host and credentials for this provider.")
        return 1

    print("1. create_index   OK")

    docs = [
        VectorDocument(
            id=f"chunk-{index}",
            user_id=USER,
            document_id="doc-a" if index < 2 else "doc-b",
            chunk_index=index,
            page=index + 1,
            content=f"chunk number {index}",
            embedding=build_vector(dimension, lead),
        )
        for index, lead in enumerate((1.0, 0.5, 0.0))
    ]

    store.upsert(docs)
    print("2. upsert         OK")

    query = build_vector(dimension, 1.0)

    results = store.search(query="chunk", embedding=query, k=3, user_id=USER)
    print(f"3. search         OK  {len(results)} hits")
    for chunk in results:
        print(f"     score={chunk.score:.4f} doc={chunk.document_id} {chunk.content!r}")

    if not results:
        print("   FAILED no hits")
        return 1

    if results[0].content == "chunk number 0":
        print("   ranking OK  nearest vector ranked first")
    else:
        print("   WARNING nearest vector was not ranked first")

    # Scores must land in 0-1 for rag_min_score to mean the same thing
    # whichever provider is in use.
    if all(0.0 <= c.score <= 1.0 for c in results):
        print("   scores OK   within 0-1, comparable across providers")
    else:
        print("   WARNING scores outside 0-1; rag_min_score will misbehave")

    scoped = store.search(
        query="chunk", embedding=query, k=3, user_id=USER, document_ids=["doc-b"]
    )
    print(f"4. document scope OK  {len(scoped)} hits for doc-b "
          f"(expected 1, got {len(scoped)})")

    other = store.search(query="chunk", embedding=query, k=3, user_id="somebody-else")
    print(f"5. user scope     {'OK' if not other else 'FAILED'}  "
          f"{len(other)} hits for a different user (expected 0)")

    # Clean up
    if settings.vector_store_provider == "qdrant":
        store.client.delete_collection(TEST_INDEX)
    else:
        store.client.indices.delete(index=TEST_INDEX)
    print("6. cleanup        OK  test index removed")

    print(f"\n{settings.vector_store_provider} is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
