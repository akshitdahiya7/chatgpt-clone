"""Profile the RAG query path and report index health.

Run from the ai-service directory:
    uv run python scripts/profile_rag.py
    uv run python scripts/profile_rag.py "your question here"

Times each stage separately so it is clear where a user's wait goes.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.embeddings.service import EmbeddingService  # noqa: E402
from app.llm.service import LLMService  # noqa: E402
from app.prompt.service import PromptService  # noqa: E402
from app.retriever.service import RetrieverService  # noqa: E402
from app.settings import get_settings  # noqa: E402
from app.vectordb.factory import VectorStoreFactory  # noqa: E402

DEFAULT_QUESTION = "What are this candidate's technical skills?"
TOP_K = 5
USER_ID = "demo-user"


def index_health(store):
    name = store.index_name
    client = store.client

    if not client.indices.exists(index=name):
        print(f"index {name!r} does not exist")
        return

    total = client.count(index=name)["count"]

    mapping = client.indices.get_mapping(index=name)[name]["mappings"]["properties"]
    embedding_type = mapping.get("embedding", {}).get("type")
    dimension = mapping.get("embedding", {}).get("dimension")

    # How many distinct documents and users are in there?
    agg = client.search(
        index=name,
        body={
            "size": 0,
            "aggs": {
                "docs": {"terms": {"field": "document_id", "size": 50}},
                "users": {"terms": {"field": "user_id", "size": 50}},
            },
        },
    )["aggregations"]

    print(f"index          : {name}")
    print(f"  chunks       : {total}")
    print(f"  embedding    : type={embedding_type} dimension={dimension}")
    print(f"  distinct docs: {len(agg['docs']['buckets'])}")
    for b in agg["docs"]["buckets"]:
        print(f"      {b['key']}  {b['doc_count']} chunks")
    print(f"  distinct users: {[b['key'] for b in agg['users']['buckets']]}")


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION
    settings = get_settings()

    print("=" * 72)
    print("INDEX HEALTH")
    print("=" * 72)
    store = VectorStoreFactory.get_provider()
    index_health(store)

    print()
    print("=" * 72)
    print("QUERY PATH TIMING")
    print("=" * 72)
    print(f"question : {question!r}")
    print(f"top_k    : {TOP_K}")
    print()

    # Construction cost is paid per request, because RAGService() is built
    # inside the endpoint rather than once at startup.
    t = time.perf_counter()
    embedding_service = EmbeddingService()
    retriever_service = RetrieverService()
    prompt_service = PromptService()
    llm_service = LLMService()
    construct = time.perf_counter() - t

    def one_pass():
        t = time.perf_counter()
        embedding = embedding_service.embed(question)
        embed = time.perf_counter() - t

        t = time.perf_counter()
        chunks = retriever_service.retrieve(
            query=question, embedding=embedding, top_k=TOP_K, user_id=USER_ID
        )
        search = time.perf_counter() - t

        t = time.perf_counter()
        prompt = prompt_service.rag(question=question, context=chunks)
        build = time.perf_counter() - t

        t = time.perf_counter()
        response = llm_service.generate(
            prompt=prompt,
            model=settings.llm_model,
            temperature=0.2,
            max_tokens=400,
            top_p=1.0,
        )
        generate = time.perf_counter() - t
        return embed, search, build, generate, chunks, prompt, response

    print("pass 1 (cold: TLS handshakes, DNS, connection pools empty)")
    cold = one_pass()
    print("pass 2 (warm: connections reused)")
    warm = one_pass()
    print("pass 3 (warm)")
    warm2 = one_pass()
    print()

    embed, search, build, generate, chunks, prompt, response = warm

    print(f"{'stage':26} {'cold':>8} {'warm':>8} {'warm2':>8}")
    print("-" * 54)
    labels = ("embed question", "opensearch search", "build prompt", "llm generate")
    for i, label in enumerate(labels):
        print(f"{label:26} {cold[i]:8.3f} {warm[i]:8.3f} {warm2[i]:8.3f}")
    print("-" * 54)
    print(f"{'query total':26} {sum(cold[:4]):8.3f} {sum(warm[:4]):8.3f} {sum(warm2[:4]):8.3f}")
    print(f"{'+ construct services':26} {construct:8.3f}  (paid once per request today)")
    print()

    print()
    prompt_chars = sum(len(m.content) for m in prompt.messages)
    context_chars = sum(len(c.content) for c in chunks)
    print(f"retrieved chunks : {len(chunks)}")
    print(f"context chars    : {context_chars}")
    print(f"prompt chars     : {prompt_chars}  (~{prompt_chars // 4} tokens)")
    print()
    print("scores (descending expected):")
    for c in chunks:
        preview = c.content[:60].replace("\n", " ")
        print(f"  {c.score:.4f}  doc={c.document_id[:8]} page={c.page}  {preview!r}")

    print()
    print("answer:")
    print(response.content[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
