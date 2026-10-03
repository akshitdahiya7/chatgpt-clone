# AWS Implementation Guide

> ## ⚠️ Verified against the live account — Changes 3 and 5 are BLOCKED
>
> Tested 2026-10-03 on account `020200817217` (AWS **Free Plan**):
>
> | Service | Result |
> |---|---|
> | S3, OpenSearch, ECR, Bedrock *control plane* | ✅ reachable |
> | **Bedrock inference** (`invoke_model`, `converse`) | ❌ `ValidationException: Operation not allowed` |
>
> Every model and call style fails identically — Titan v1 and v2, Nova Lite, with and without the
> `us.` prefix. This is an account-plan restriction, not a model-access or credentials problem.
> Only upgrading off the Free Plan clears it.
>
> **Therefore: skip Change 3 and Change 5.**
> - Embeddings stay on `sentence-transformers` / HuggingFace, `EMBEDDING_DIMENSION=384`
> - LLM stays on GitHub Models (free with the Student Pack, already implemented)
>
> Consequences: ai-service keeps PyTorch, so it stays ~1.5 GB RAM (t3.small minimum) and its image
> stays ~3 GB (over ECR's 500 MB free tier, ~$0.25/mo). **Pull images from ECR rather than building
> on the EC2 box** — building PyTorch on 2 GB tends to OOM.
>
> Also: the IAM user needs **`AmazonEC2FullAccess`** added. The four policies in `AWS_SETUP.md`
> Step 2 omit EC2, so `ec2 describe_instances` fails with `UnauthorizedOperation`.


Migrating this project from Azure to AWS. Written as a build order — each change is
self-contained and verifiable before you move to the next.

**Target stack:** S3 (files) · Bedrock (embeddings + optional LLM) · OpenSearch (vectors) ·
ECR (images) · EC2 + docker-compose (compute) · Amplify (frontend)

**Budget:** ~$45–50/month against $100 credits, expiring **Mar 13 2027**.

> **Design principle:** every Azure provider stays in place. All three subsystems already use
> factories, so AWS providers are *added alongside* and selected by env var. You keep the ability
> to run locally with no cloud at all — which matters, because you do not want to burn Bedrock
> calls while debugging a chunker.

---

## Build order

| # | Change | Service | Needs AWS? |
|---|---|---|---|
| **0** | Fix `BaseVectorStore` contract | ai-service | No |
| **1** | AWS account prep | — | Console |
| **2** | S3 storage provider + factory | chat-service | Yes |
| ~~3~~ | ~~Bedrock embeddings~~ — **BLOCKED, skip** | ai-service | — |
| **4** | OpenSearch vector store provider | ai-service | Yes |
| **5** | Bedrock LLM provider | ai-service | Yes |
| **6** | docker-compose + EC2 | root | Yes |
| **7** | ECR + CI | `.github` | Yes |
| **8** | Amplify frontend | Console | Yes |

Do **0** now — it costs nothing and unblocks 4.

---

# Change 0 — Fix the `BaseVectorStore` contract

**Problem:** `app/vectordb/providers/base.py` declares signatures that neither the caller nor the
existing Azure provider match.

| Method | ABC says | Reality (`service.py` + `azure_ai_search.py`) |
|---|---|---|
| `create_index` | `(self)` | `(self, recreate: bool = False)` |
| `upsert` | `(self, documents)` | `(self, docs)` |
| `search` | `(self, embedding, top_k=5) -> list[VectorDocument]` | `(self, query, embedding, k) -> list[RetrievedChunk]` |

The ABC is lying. Any new provider written against it breaks on first call.

**Fix:** edit `app/vectordb/providers/base.py` so the abstract methods read:

```python
def create_index(self, recreate: bool = False) -> None: ...
def upsert(self, docs: list[VectorDocument]) -> None: ...
def search(self, query: str, embedding: list[float], k: int) -> list[RetrievedChunk]: ...
```

Import `RetrievedChunk` alongside `VectorDocument`. Don't change the Azure provider — it's already
correct; the base class is what's wrong.

**Note on `query`:** the Azure provider does *hybrid* search (BM25 text + vector). Your OpenSearch
provider can accept `query` and ignore it for pure k-NN — simpler, and fine for a first pass. Keep
the parameter so the interface stays uniform.

**Verify:** `uv run python -c "from app.vectordb.service import VectorStoreService"` still imports.

---

# Change 1 — AWS account prep

## 1a. Budget alert — before anything else

**Billing and Cost Management → Budgets → Create budget**
- Monthly cost budget, **$50**, alerts at 50/80/100% to your email

## 1b. Use `us-east-1` for everything

Not Mumbai. Two reasons: Bedrock model availability is much better in `us-east-1`, and mixing
regions bills you for cross-region data transfer. The ~250ms extra latency is invisible next to
LLM inference.

## 1c. IAM user (not root)

**IAM → Users → Create user** → `chatgpt-clone-dev`, programmatic access only.

Attach: `AmazonS3FullAccess`, `AmazonBedrockFullAccess`,
`AmazonOpenSearchServiceFullAccess`, `AmazonEC2ContainerRegistryFullAccess`.

> These are broad. Production uses policies scoped to specific resource ARNs. Acceptable for a
> short-lived student project; don't present it as the pattern you'd ship.

**Security credentials → Create access key** → *Application running outside AWS*:

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

Shown once. Save straight into your `.env` files.

## 1d. Request Bedrock model access

**Bedrock → Model access → Modify model access.** Start now; it gates Changes 3 and 5.

- **Amazon Titan Text Embeddings V2** → Change 3
- **Amazon Nova Lite** or **Claude 3.5 Haiku** → Change 5

Amazon's own models are usually instant. Anthropic models may need a short use-case form.

---

# Change 2 — S3 storage provider

**Goal:** replace Blob Storage, and stop `chat.py` importing a concrete Azure class.

## Files

| Action | Path |
|---|---|
| Create | `chat-service/app/services/base.py` |
| Create | `chat-service/app/services/s3_storage.py` |
| Create | `chat-service/app/services/factory.py` |
| Edit | `chat-service/app/api/v1/chat.py` |
| Edit | `chat-service/app/settings.py`, `pyproject.toml` |

## Dependency

```bash
cd chat-service && uv add boto3
```

## The interface

`azure_blob.py` already defines the shape — mirror it exactly so both are interchangeable.
Write `base.py` as an ABC:

```python
class BaseStorageService(ABC):
    @abstractmethod
    def generate_sas_url(self, blob_name: str, expiry_minutes: int = 60) -> str: ...

    @abstractmethod
    async def upload_file(self, file) -> dict: ...
```

`upload_file` must return the same keys the frontend already consumes:
`blob_name`, `filename`, `content_type`, `url`, `sas_url`.

> Keep the Azure-flavoured names (`blob_name`, `sas_url`) even for S3. Renaming them means
> touching the frontend too. Ugly but contained — note it as debt, don't fix it now.

## S3 specifics

**Client:**
```python
boto3.client(
    "s3",
    region_name=settings.aws_region,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
)
```

**Presigned URL** — the direct analogue of `generate_blob_sas`:
```python
client.generate_presigned_url(
    "get_object",
    Params={"Bucket": bucket, "Key": key},
    ExpiresIn=expiry_minutes * 60,   # note: SECONDS, not minutes
)
```

**Upload:**
```python
client.put_object(Bucket=bucket, Key=key, Body=content, ContentType=file.content_type)
```

Keep the existing `uuid4().hex + extension` key scheme.

## Gotchas

- **`ExpiresIn` is seconds.** The Azure version takes minutes. Easy off-by-60 bug.
- **Max presigned expiry is 7 days** with IAM user keys. Your 60 min is fine.
- **Leave Block Public Access ON.** Presigned URLs work regardless — that's the point. A public
  bucket would defeat the access control you already have.
- **Bucket names are globally unique**, lowercase, no underscores. Try `chatgpt-clone-<initials>`.
- **`url` vs `sas_url`:** the plain S3 object URL is *not* publicly fetchable with Block Public
  Access on. Return it for reference, but the frontend must use `sas_url`.
- `AzureBlobService.__init__` calls `create_container()` on every boot. Don't mirror that —
  create the bucket once in the console. Calling `create_bucket` on every start is a needless
  API call that fails confusingly if the name is taken.

## Factory + settings

`factory.py` switches on `settings.storage_provider` (`"azure"` | `"s3"`), same shape as
`LLMFactory`. Validate credentials are present and raise a clear error — follow the pattern
already in `ai-service/app/llm/factory.py`.

Add to `chat-service/app/settings.py`:
```python
storage_provider: str = "s3"
aws_region: str = "us-east-1"
aws_access_key_id: str = ""
aws_secret_access_key: str = ""
s3_bucket_name: str = ""
```
Make the four Azure storage fields default to `""` so the service boots without them.

In `chat.py`, replace the module-level `azure_service = AzureBlobService()` with
`storage_service = StorageFactory.get_provider()`.

> Module-level instantiation means a bad config crashes at import, not at request time. That's
> arguably good (fail fast) but makes tests awkward. Leave as-is for now; a FastAPI dependency
> would be the cleaner fix later.

## Create the bucket

**S3 → Create bucket** → `us-east-1`, Block Public Access **ON**, versioning off.

## Verify

Start chat-service, `POST /api/v1/chat` with a file, confirm: 200 response, object appears in the
bucket, and pasting `sas_url` into a browser downloads the file.

---

# Change 3 — Bedrock embeddings provider

**Goal:** drop `sentence-transformers` (and PyTorch) from the deployed image.

This is the change that pays for the others: ai-service goes from ~1.5GB RAM to ~200MB, and its
image from ~3GB to ~300MB — which is what lets a t3.small host everything and the image fit ECR's
free tier.

## Files

| Action | Path |
|---|---|
| Create | `ai-service/app/embeddings/providers/bedrock.py` |
| Edit | `ai-service/app/embeddings/factory.py`, `settings.py`, `pyproject.toml` |

```bash
cd ai-service && uv add boto3
```

## Implement `BaseProvider`

Already defined: `embed(text) -> list[float]` and `embed_batch(texts) -> list[list[float]]`.

**Client:** `boto3.client("bedrock-runtime", region_name=...)` — note **`bedrock-runtime`**, not
`bedrock`. The latter is the control plane and won't have `invoke_model`.

**Single embed:**
```python
body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
resp = client.invoke_model(modelId="amazon.titan-embed-text-v2:0", body=body)
embedding = json.loads(resp["body"].read())["embedding"]
```

## ⚠️ The batch problem

**Titan embeds exactly one text per API call.** There is no batch endpoint. So `embed_batch` has
to loop — and a 200-chunk PDF becomes 200 sequential HTTPS round-trips, which is slow (~30–60s).

Three ways to handle it, pick one:

1. **Sequential loop** — simplest, correct, slow. Fine to start.
2. **`ThreadPoolExecutor`**, 8–10 workers — ~10x faster, ~20 extra lines. Recommended once
   correctness is proven. boto3 clients are thread-safe for this.
3. **Switch to `cohere.embed-english-v3`**, which *does* batch natively (up to 96 texts per call
   via a `texts` array). Needs separate Cohere model access, and a different request/response
   shape — `{"texts": [...], "input_type": "search_document"}`.

Start with 1, move to 2. `embedding_batch_size` in settings becomes meaningless for Titan — leave
it alone rather than deleting it, since the HuggingFace provider still uses it.

## ⚠️ Dimension change — read this

| Provider | Dimensions |
|---|---|
| `all-MiniLM-L6-v2` (current) | **384** |
| Titan Text Embeddings V2 | **1024** (configurable: 256 / 512 / 1024) |

**Vector dimensions are fixed when the index is created.** Switching embedding providers means:

1. Set `EMBEDDING_DIMENSION` to match
2. **Recreate the index** (`create_index(recreate=True)`)
3. **Re-embed and re-upload every document** — old vectors are unusable

Nothing is indexed yet, so this is free right now. It won't be later.

A mismatch between `EMBEDDING_DIMENSION` and what the provider actually returns gives you either
a confusing index-time rejection or, worse, silently garbage search results. Keep them in lockstep.

> You could set Titan to 256 dimensions for cheaper storage and faster search, at some recall
> cost. 1024 is the safer default; 384 won't make it compatible with existing MiniLM vectors —
> different models produce incompatible embedding spaces regardless of matching dimensions.

## Settings

```python
embedding_provider: str = "bedrock"   # "huggingface" | "bedrock"
embedding_model: str = "amazon.titan-embed-text-v2:0"
embedding_dimension: int = 1024
aws_region: str = "us-east-1"
aws_access_key_id: str = ""
aws_secret_access_key: str = ""
```

**Keep the HuggingFace provider.** Use `huggingface` locally (free, offline, no API latency) and
`bedrock` in deployment. That's the whole point of the factory — and it means a dimension-384 dev
index and a dimension-1024 prod index, which is fine as long as they're separate indexes.

## Verify

```python
from app.embeddings.service import EmbeddingService
e = EmbeddingService()
v = e.embed("hello world")
print(len(v))            # 1024
print(sum(x*x for x in v) ** 0.5)   # ~1.0 if normalize worked
```

## Then shrink the image

Once Bedrock works, move `sentence-transformers` out of the main dependencies in `pyproject.toml`
into an optional group. Rebuild and confirm the image drops to a few hundred MB.

---

# Change 4 — OpenSearch vector store provider

## Create the domain first

**OpenSearch Service → Create domain**

| Field | Value |
|---|---|
| Name | `chatgpt-clone-search` |
| Standby | **Disabled** |
| Instance | **`t3.small.search`**, 1 node |
| Storage | 10 GB gp3 |
| Network | **Public access** (a VPC domain can't be reached from your laptop) |
| Fine-grained access control | **Enabled**, create master user |
| Access policy | Allow open access *within* fine-grained control |

> ⚠️ **OpenSearch cannot be stopped or paused.** It bills ~$26/month from creation until you
> **delete** it. Set your deletion reminder now.

**Auth choice:** master username/password (HTTP basic) is far less friction than SigV4 for
development. SigV4 is the better practice; basic auth gets you working today. Your call, but
don't spend an evening debugging request signing.

## Files

| Action | Path |
|---|---|
| Create | `ai-service/app/vectordb/providers/opensearch.py` |
| Edit | `providers/__init__.py`, `factory.py`, `settings.py`, `pyproject.toml` |

```bash
cd ai-service && uv add opensearch-py
```

## Client

Basic auth:
```python
from opensearchpy import OpenSearch, RequestsHttpConnection

client = OpenSearch(
    hosts=[{"host": host, "port": 443}],   # host only — strip https://
    http_auth=(master_user, master_password),
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)
```

SigV4 instead, if you prefer:
```python
from opensearchpy import AWSV4SignerAuth
auth = AWSV4SignerAuth(boto3.Session().get_credentials(), region, "es")
```
Service name is `"es"` for managed OpenSearch (`"aoss"` is Serverless — wrong here).

## `create_index(recreate=False)`

Mirror the Azure logic: check existence via `client.indices.exists(index)`, delete if `recreate`,
else return early.

The mapping — this is the part worth getting right:

```python
{
  "settings": {"index": {"knn": True}},
  "mappings": {
    "properties": {
      "user_id":     {"type": "keyword"},
      "document_id": {"type": "keyword"},
      "chunk_index": {"type": "integer"},
      "page":        {"type": "integer"},
      "content":     {"type": "text"},
      "embedding": {
        "type": "knn_vector",
        "dimension": self.embedding_dimension,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "lucene",
        },
      },
    }
  },
}
```

- **`"knn": True` in settings is mandatory.** Without it the `knn_vector` field is rejected.
- **`keyword` not `text`** for the id fields — `text` gets analyzed and won't filter exactly.
  This is the OpenSearch equivalent of Azure's `filterable=True`.
- **`space_type: cosinesimil`** matches your normalized embeddings. Use `l2` only if you stop
  normalizing.
- `engine: lucene` supports filtered k-NN; `nmslib` is faster at scale but you have neither the
  data volume nor the need.

## `upsert(docs)`

Use the bulk helper, not a loop of `index()` calls:

```python
from opensearchpy import helpers
actions = [
    {"_index": self.index_name, "_id": doc.id, "_source": doc.to_dict()}
    for doc in docs
]
helpers.bulk(client, actions)
```

`VectorDocument.to_dict()` already drops `score` when `None` — good, you don't want it indexed.

## `search(query, embedding, k)`

```python
body = {
    "size": k,
    "query": {"knn": {"embedding": {"vector": embedding, "k": k}}},
    "_source": ["id", "user_id", "document_id", "chunk_index", "page", "content"],
}
resp = client.search(index=self.index_name, body=body)
```

Map each `hit` to `RetrievedChunk(content=..., page=..., document_id=..., score=hit["_score"])`,
reading fields from `hit["_source"]`.

**Return `RetrievedChunk`, not `VectorDocument`** — match the Azure provider and the fixed ABC
from Change 0.

## Gotchas

- **Scores aren't comparable to Azure's.** OpenSearch `cosinesimil` returns roughly
  `(1 + cosine) / 2` in `[0, 1]`; Azure uses its own scale. Good news: nothing filters on score —
  `app/rag/service.py` only displays it — so no threshold needs re-tuning. Just don't compare
  score values across providers.
- **`app/rag/test.py:67` reads `doc['@search.score']`**, which is an Azure-only response field.
  It will `KeyError` against OpenSearch. That script talks to the Azure SDK directly instead of
  going through `VectorStoreService`, so it bypasses the factory entirely — either port it to the
  service layer or leave it as Azure-only and don't run it.
- **Strip the scheme** from the endpoint. The console shows `https://search-...`; the client
  wants the bare host plus `port=443`.
- **New indexes take a few seconds to become searchable.** A `create_index` immediately followed
  by `search` can return empty. Use `client.indices.refresh(index)` in tests.
- **`t3.small.search` has ~2GB heap.** Plenty for your volume; it will not love 10k+ documents.

## Settings

```python
vector_store_provider: str = "opensearch"   # "azure" | "opensearch"
opensearch_host: str = ""        # bare host, no https://
opensearch_user: str = ""
opensearch_password: str = ""
azure_search_endpoint: str = ""  # relax to optional
azure_search_key: str = ""       # relax to optional
```

Relaxing the two Azure fields matters — they're currently required, so ai-service won't boot
without them even on `opensearch`.

## Verify

```python
s = VectorStoreService()
s.create_index(recreate=True)
s.upsert([...one VectorDocument...])
print(s.search("test", embedding, 3))
```

---

# Change 5 — Bedrock LLM provider

GitHub Models stays the default (free, already working). This gives you a fully-AWS demo option.

## Files

`ai-service/app/llm/providers/bedrock.py` + a `case "bedrock"` in `factory.py`.

## Use the Converse API

`client.converse(...)` normalizes request/response across Bedrock models — Nova, Claude, Llama all
take the same shape. Don't use raw `invoke_model` with per-model JSON; it's needless work.

```python
resp = client.converse(
    modelId=self.model,
    messages=[{"role": m.role, "content": [{"text": m.content}]} for m in messages],
    system=[{"text": system_prompt}],          # if you have one
    inferenceConfig={"temperature": 0.2, "topP": 1.0, "maxTokens": 2048},
)
text = resp["output"]["message"]["content"][0]["text"]
```

Return `LLMResponse(content=text, model=self.model)`.

## ⚠️ Three shape mismatches with your `ChatMessage`

1. **System messages are a separate parameter.** Bedrock rejects `role: "system"` inside
   `messages`. You must partition: pull system messages out into the `system=[...]` argument,
   pass the rest as `messages`. Check what `app/prompt/builder.py` emits — if it puts a system
   message first, this *will* bite you.
2. **Content is a list of blocks**, not a string: `[{"text": ...}]`.
3. **Roles must alternate** user/assistant, starting with user. Two consecutive user messages are
   an error — unlike the GitHub provider, which tolerates it.

## Model IDs

- `amazon.nova-lite-v1:0` — cheapest, fine for RAG answers
- `anthropic.claude-3-5-haiku-20241022-v1:0` — better quality

> Some models require a **cross-region inference profile** — the ID gets a region prefix, e.g.
> `us.anthropic.claude-3-5-haiku-20241022-v1:0`. If you get `ValidationException: Invalid model
> identifier` on a model you *have* been granted, try the `us.` prefix before assuming the access
> request failed.

## Streaming

`GithubLLMProvider.stream()` raises `NotImplementedError`, so nothing calls it. Bedrock's
equivalent is `converse_stream()` if you implement it later — but do it for both providers or
neither, so behaviour doesn't depend on config.

## Settings

```python
llm_provider: str = "github"     # keep github as default
bedrock_model: str = "amazon.nova-lite-v1:0"
```

---

# Change 6 — docker-compose + EC2

## The compose file

Create `docker-compose.yml` at the repo root with the three services, ports `8000:8000`,
`8001:8001`, `8002:8002`. Point `CHAT_SERVICE` and `AI_SERVICE_URL` at **service names**
(`http://ai-service:8002`), not localhost — inside the compose network, localhost is the container
itself.

Use `env_file:` per service rather than inlining secrets. Add `restart: unless-stopped`.

## EC2 instance

| Field | Value |
|---|---|
| AMI | Amazon Linux 2023 |
| Type | **t3.small** (2GB — t3.micro's 1GB is not enough) |
| Key pair | create and download the `.pem` |
| Storage | 16 GB gp3 |
| Security group | SSH 22 **from your IP only**; TCP 8001 from anywhere |

Only expose 8001 — that's the only port the frontend actually calls.

Then: install Docker, add `ec2-user` to the `docker` group, log out and back in, install the
compose plugin, clone the repo, create the `.env` files, `docker compose up -d`.

## ⚠️ The IP problem

A stopped instance gets a **new public IP** on restart, and `NEXT_PUBLIC_API_URL` is baked into
the frontend at build time — so every restart breaks the deployed frontend.

| Fix | Cost |
|---|---|
| **Elastic IP** | ~$3.60/mo, stable, zero hassle |
| DuckDNS + boot script | $0, a little setup |
| Rebuild frontend each time | $0, a manual step while you're nervous |

Pay the $3.60.

## Cost control

Stopped instances bill **$0 compute** — only ~$1.30/mo for the EBS volume. Stop it when you're
not demoing; a 4-hour session costs ~$0.08. Note this does **not** apply to OpenSearch, which
bills continuously until deleted.

---

# Change 7 — ECR + CI

## Create repositories

**ECR → Create repository**, private, one each: `gateway`, `chat-service`, `ai-service`.

Free tier is 500MB — which the ai-service image only fits *after* Change 3 removes PyTorch.

## Rewrite `.github/workflows/backend.yml`

Replace the Azure login and ACR steps with:

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: us-east-1

- uses: aws-actions/amazon-ecr-login@v2
  id: login-ecr
```

Then tag as `${{ steps.login-ecr.outputs.registry }}/${{ matrix.service }}:${{ github.sha }}`.

Delete the now-unused `AZURE_*` and `ACR_*` secrets.

> Access keys in secrets are the quick path. **OIDC via `role-to-assume` is the better one** — no
> long-lived credentials in GitHub. You already did this dance for Azure in `AZURE_SETUP.md`
> Step 7; the AWS equivalent is an IAM role with a GitHub OIDC trust policy. Worth doing if you
> want the workflow to be something you'd show off.

Keep `.dockerignore` in mind — it's what stops your `.env` being baked into these images.

---

# Change 8 — Amplify frontend

**Amplify → Create new app → GitHub** → authorize → your repo, `main`.

- Framework auto-detects Next.js
- **App root directory: `frontend`** (it won't find it otherwise)
- Environment variable: `NEXT_PUBLIC_API_URL` = `http://<elastic-ip>:8001`

⚠️ **Mixed content:** Amplify serves HTTPS; your EC2 backend is plain HTTP. Browsers block
HTTPS→HTTP requests, so **the deployed frontend cannot call your backend over HTTP**. Options:

- Put a reverse proxy (Caddy) on EC2 with a real domain — Caddy gets you Let's Encrypt automatically
- Use a CloudFront distribution in front of EC2 to terminate TLS
- For a quick demo only: run the frontend locally against the EC2 IP

**Don't discover this on interview morning.** It's the most likely thing to break in the whole
setup, and it has nothing to do with your code.

Delete `.github/workflows/azure-static-web-apps-*.yml` once Amplify works.

---

# Verification checklist

1. `/docs` loads on all three services
2. Upload a PDF → object lands in S3, `sas_url` downloads it
3. OpenSearch → Indices shows `documents` with a non-zero count
4. Ask a question about the document → grounded answer
5. Switch `LLM_PROVIDER` between `github` and `bedrock` → both answer
6. Stop and start the EC2 instance → stack comes back via `restart: unless-stopped`

---

# Teardown — do not skip

In this order:

1. **Delete the OpenSearch domain** — the expensive one, ~$26/mo, cannot be paused
2. **Terminate the EC2 instance** (terminate, not stop)
3. **Release the Elastic IP** — an unattached EIP still bills
4. Empty and delete the S3 bucket
5. Delete the ECR repositories
6. Delete the Amplify app
7. Check **Billing → Bills** a day later and confirm $0 forecast

An unreleased Elastic IP and a running OpenSearch domain are the two things most likely to quietly
eat the rest of your credits.

---

# Known gaps (unchanged by this migration)

- `mongodb_uri` is configured but unused — no Mongo client exists anywhere
- The gateway is deployed but bypassed; the frontend calls chat-service directly
- `AzureOpenAIProvider.generate()` is an empty stub
- Streaming is unimplemented in every LLM provider
- CORS is `allow_origins=["*"]` in chat-service and ai-service
- `storage_provider` returns Azure-shaped keys (`blob_name`, `sas_url`) regardless of backend
