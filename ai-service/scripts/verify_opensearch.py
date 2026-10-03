"""Round-trip the OpenSearch vector store: create index, upsert, search, clean up.

Run from the ai-service directory, once the domain is Active:
    uv run python scripts/verify_opensearch.py

Uses a throwaway index, so it cannot disturb real data.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.settings import get_settings  # noqa: E402
from app.vectordb.models import VectorDocument  # noqa: E402
from app.vectordb.providers import OpenSearchVectorStore  # noqa: E402

TEST_INDEX = "verify-roundtrip"

POLICY_HELP = """  -> The domain access policy is denying this request.
     Wait for BOTH 'Domain processing status: Active' and
     'Configuration change status: Completed'. If it still fails:
     Security configuration -> Edit -> Access policy ->
     'Only use fine-grained access control' -> Save."""


def build_vector(dimension, lead):
    """A deterministic unit-ish vector, distinguishable by its first element."""
    vector = [0.0] * dimension
    vector[0] = lead
    vector[1] = 1.0 - lead
    return vector


def connect(settings):
    store = OpenSearchVectorStore(
        host=settings.opensearch_host,
        user=settings.opensearch_user,
        password=settings.opensearch_password,
        index_name=TEST_INDEX,
    )

    info = store.client.info()
    version = info["version"]
    print("connected : {} {}".format(version["distribution"], version["number"]))
    return store


def main():
    settings = get_settings()

    host = settings.opensearch_host
    if not host:
        sys.exit("OPENSEARCH_HOST is empty in .env")
    if "xxxxx" in host:
        sys.exit(
            "OPENSEARCH_HOST is still the placeholder.\n"
            "  Copy 'Domain endpoint (IPv4)' from the console, without https://"
        )

    dimension = settings.embedding_dimension
    print(f"host      : {host}")
    print(f"dimension : {dimension}")

    try:
        store = connect(settings)
    except Exception as exc:
        detail = str(exc)
        print(f"\nFAILED to connect: {type(exc).__name__}: {detail[:200]}")

        if "resource-based policy" in detail or "anonymous" in detail:
            print(POLICY_HELP)
        elif "401" in detail or "Unauthorized" in detail:
            print("  -> Wrong OPENSEARCH_USER or OPENSEARCH_PASSWORD.")
        else:
            print("  -> Domain still creating, or wrong host.")

        return 1

    store.create_index(recreate=True)
    print("1. create_index   OK")

    docs = [
        VectorDocument(
            id=f"chunk-{index}",
            user_id="user-1",
            document_id="doc-1",
            chunk_index=index,
            page=index + 1,
            content=f"chunk number {index}",
            embedding=build_vector(dimension, lead),
        )
        for index, lead in enumerate((1.0, 0.5, 0.0))
    ]

    store.upsert(docs)
    count = store.client.count(index=TEST_INDEX)["count"]
    print(f"2. upsert         OK  {count} docs indexed")

    results = store.search(query="chunk", embedding=build_vector(dimension, 1.0), k=3)
    print(f"3. search         OK  {len(results)} hits")
    for chunk in results:
        print(f"     page={chunk.page} score={chunk.score:.4f} content={chunk.content!r}")

    if not results:
        print("   FAILED no hits returned")
        return 1

    if results[0].content == "chunk number 0":
        print("   ranking OK  nearest vector ranked first")
    else:
        print("   WARNING nearest vector was not ranked first")

    store.client.indices.delete(index=TEST_INDEX)
    print("4. cleanup        OK  test index removed")

    print("\nOpenSearch vector store is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
