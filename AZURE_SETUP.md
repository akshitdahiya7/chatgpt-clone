# Azure Setup — Portal Walkthrough

Click-through setup for this repo on an **Azure for Students** subscription (GitHub Education Pack).
Every step lists the exact settings to pick and the env vars it produces.

Work through the steps in order — later steps consume values produced by earlier ones.

---

## Architecture you are building

```
Static Web Apps (frontend)
        │  NEXT_PUBLIC_API_URL
        ▼
  chat-service  ──────►  Blob Storage   (file uploads + SAS URLs)
        │  AI_SERVICE_URL
        ▼
   ai-service   ──────►  Azure AI Search (vector store)
        │
        └───────────►  GitHub Models    (LLM)

   gateway  ──► chat-service   (deployed, but the frontend does not call it today)
```

> **Note on the gateway:** `frontend/app/components/upload.tsx` points `NEXT_PUBLIC_API_URL`
> straight at **chat-service**, not the gateway. The gateway is deployed and healthy but sits
> outside the request path until you repoint the frontend at it. Set `NEXT_PUBLIC_API_URL`
> to the **chat-service** URL unless you change that first.

---

## Cost expectations on $100 student credit

| Resource | Tier to pick | Cost |
|---|---|---|
| Azure AI Search | **Free** | $0 — 50 MB, 3 indexes, 1 free service per subscription |
| Blob Storage | Standard LRS, Hot | Pennies/month at dev volume |
| Container Apps | Consumption | $0 within the monthly free grant (180k vCPU-s, 360k GiB-s, 2M requests) |
| Container Registry | **Basic** | **~$5/month — the only guaranteed recurring charge.** No free ACR tier exists |
| Static Web Apps | **Free** | $0 |
| GitHub Models | Free w/ Student Pack | $0, rate-limited |

**Azure OpenAI is not part of this setup.** Student subscriptions generally cannot get Azure OpenAI
access, and `ai-service/app/llm/providers/azure_openai.py` is an empty stub anyway. GitHub Models is
the working path — it is already implemented in `github.py`.

---

## Step 0 — Activate Azure for Students

1. Go to <https://azure.microsoft.com/free/students> and sign in with the GitHub-verified account.
2. Verify with your student email. **No credit card is required** on this offer.
3. You get $100 credit valid 12 months, plus a set of always-free services.

Confirm at <https://portal.azure.com> → **Subscriptions** that you see *Azure for Students*.

---

## Step 1 — Resource group

**Portal → Resource groups → Create**

| Field | Value |
|---|---|
| Subscription | Azure for Students |
| Name | `chatgpt-clone-rg` |
| Region | `Central India` (or nearest — **AI Search Free tier is not in every region**; if Free is unavailable later, come back and use `East US`) |

Put every resource below in this group so you can delete the whole stack in one click.

---

## Step 2 — Blob Storage (chat-service uploads)

**Portal → Storage accounts → Create**

| Field | Value |
|---|---|
| Resource group | `chatgpt-clone-rg` |
| Storage account name | `chatgptclonest<yourinitials>` (3–24 chars, lowercase+digits only, globally unique) |
| Region | same as the resource group |
| Primary service | Azure Blob Storage |
| Performance | Standard |
| Redundancy | **LRS** (cheapest; GRS doubles the cost for no dev benefit) |

Leave the other tabs at defaults → **Review + create**.

### Create the container

Open the account → **Data storage → Containers → + Container**

- Name: `uploads`
- Anonymous access level: **Private (no anonymous access)**

Private is correct — `azure_blob.py` hands out time-limited **SAS URLs** (60 min) rather than
public blobs, so the container must stay private for that to be meaningful.

### Collect the env vars

Open the account → **Security + networking → Access keys → Show keys**, use **key1**:

```
AZURE_STORAGE_ACCOUNT_NAME=<the name you chose>
AZURE_STORAGE_ACCOUNT_KEY=<key1 "Key">
AZURE_STORAGE_CONNECTION_STRING=<key1 "Connection string">
AZURE_STORAGE_CONTAINER_NAME=uploads
```

`azure_blob.py` needs **both** the connection string (to build the client) and the bare account
key (to sign SAS tokens) — they are not interchangeable, so copy both.

---

## Step 3 — Azure AI Search (vector store)

**Portal → search for "AI Search" → Create**

| Field | Value |
|---|---|
| Resource group | `chatgpt-clone-rg` |
| Service name | `chatgpt-clone-search` (becomes `https://chatgpt-clone-search.search.windows.net`) |
| Location | same region; if **Free** is greyed out, try `East US` |
| Pricing tier | **Free** — click *Change Pricing Tier* and select Free |

> **Free tier limits:** 50 MB total storage, 3 indexes, no SLA, and **one free service per
> subscription**. Vector search works. 50 MB is fine for a few hundred document chunks; if you
> hit the ceiling, upgrading means deleting and recreating the service at Basic (~$75/mo — likely
> more than your credit allows, so prefer pruning the index).

### Collect the env vars

- **Overview → Url** → `AZURE_SEARCH_ENDPOINT`
- **Settings → Keys → Primary admin key** → `AZURE_SEARCH_KEY`

Use the **admin** key, not a query key. `azure_ai_search.py` calls `create_index()` and
`delete_index()` via `SearchIndexClient`, which query keys cannot do.

```
AZURE_SEARCH_ENDPOINT=https://chatgpt-clone-search.search.windows.net
AZURE_SEARCH_KEY=<primary admin key>
AZURE_SEARCH_INDEX=documents
```

**Do not create the index by hand** — the app creates it with the correct HNSW vector profile and
a 384-dimension vector field. A hand-made index will have the wrong schema.

> **Dimension lock-in:** the index is created with `EMBEDDING_DIMENSION=384`, matching
> `all-MiniLM-L6-v2`. Vector dimensions are fixed at index creation. If you ever change the
> embedding model, you must change `EMBEDDING_DIMENSION` *and* delete + recreate the index.

---

## Step 4 — GitHub Models token (the LLM)

Free with the Student Pack, and already implemented in `ai-service/app/llm/providers/github.py`.

1. <https://github.com/settings/tokens> → **Generate new token (fine-grained)**
2. Expiration: 90 days
3. **Permissions → Account permissions → Models → Read-only**
4. Generate and copy it immediately — GitHub shows it once.

```
LLM_PROVIDER=github
LLM_MODEL=openai/gpt-4o-mini
MODEL_TOKEN=<the PAT>
```

Browse available model IDs at <https://github.com/marketplace/models>. The ID must be the full
slug (`openai/gpt-4o-mini`), not just `gpt-4o-mini`.

---

## Step 5 — Run it locally first

Prove the Azure resources work before adding deployment on top. Copy each template and fill in
the values you collected:

```powershell
cp gateway/.env.example       gateway/.env
cp chat-service/.env.example  chat-service/.env
cp ai-service/.env.example    ai-service/.env
# then edit each .env with the values from Steps 2-4
```

`.env` is gitignored; `.env.example` is committed. Never put real keys in `.env.example`.

Run each service in its own terminal:

```powershell
cd ai-service    ; uv run uvicorn app.main:app --reload --port 8002
cd chat-service  ; uv run uvicorn app.main:app --reload --port 8001
cd gateway       ; uv run uvicorn app.main:app --reload --port 8000
cd frontend      ; npm run dev
```

First ai-service start downloads the `all-MiniLM-L6-v2` weights (~90 MB) and is slow — this is
normal. Check <http://localhost:8002/docs> and <http://localhost:8001/docs> before moving on.

---

## Step 6 — Container Registry

**Portal → Container registries → Create**

| Field | Value |
|---|---|
| Resource group | `chatgpt-clone-rg` |
| Registry name | `chatgptclonecr<yourinitials>` (alphanumeric only, globally unique) |
| Location | same region |
| Pricing plan | **Basic** |

After creation, open **Settings → Access keys** and tick **Admin user = Enabled**
(Container Apps uses this to pull images in the simple setup below).

Record from the **Overview** blade:

```
ACR_NAME=chatgptclonecr<yourinitials>
ACR_LOGIN_SERVER=chatgptclonecr<yourinitials>.azurecr.io
```

These are exactly the two secrets `.github/workflows/backend.yml` already expects.

---

## Step 7 — GitHub Actions → Azure auth (OIDC)

`backend.yml` uses `azure/login@v2` with **no client secret**, which means it authenticates via
OIDC federated credentials. Set that up:

### 7a. App registration

**Portal → Microsoft Entra ID → App registrations → New registration**

- Name: `chatgpt-clone-github-actions`
- Supported account types: **Single tenant**
- Redirect URI: leave blank → **Register**

From the app's **Overview**, copy **Application (client) ID** and **Directory (tenant) ID**.

### 7b. Federated credentials

In the app → **Certificates & secrets → Federated credentials → Add credential**

- Scenario: **GitHub Actions deploying Azure resources**
- Organization: `Im-Shivam-Singh` · Repository: `chatgpt-clone`
- Entity type: **Branch** · Branch: `main`
- Name: `github-main`

Add a **second** credential with Entity type **Pull request** if you want PR builds to
authenticate too.

> Federated credentials are per-entity. A `main` branch credential does **not** cover tags,
> other branches, or environments — add one credential per entity you deploy from.

### 7c. Grant it access to the registry

**Resource group `chatgpt-clone-rg` → Access control (IAM) → Add role assignment**

- Role: **AcrPush**
- Members: select `chatgpt-clone-github-actions`

Repeat with role **Contributor** if you later want Actions to update Container Apps too.

### 7d. Repository secrets

**GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | Application (client) ID from 7a |
| `AZURE_TENANT_ID` | Directory (tenant) ID from 7a |
| `AZURE_SUBSCRIPTION_ID` | Portal → Subscriptions → your subscription ID |
| `ACR_NAME` | from Step 6 |
| `ACR_LOGIN_SERVER` | from Step 6 |

Push to `main` (or run the workflow manually) and confirm three images appear under
**Container registry → Services → Repositories**.

---

## Step 8 — Container Apps

**Portal → Container Apps → Create**. Do this three times — once per service.

### Shared environment (created with the first app)

On the **Basics** tab, next to *Container Apps Environment*, click **Create new**:

- Name: `chatgpt-clone-env`
- Zone redundancy: **Disabled** (redundancy costs money)

Reuse this same environment for apps 2 and 3.

### Per-app settings

| | gateway | chat-service | ai-service |
|---|---|---|---|
| App name | `gateway` | `chat-service` | `ai-service` |
| Image source | Azure Container Registry | same | same |
| Image | `gateway` | `chat-service` | `ai-service` |
| Tag | `latest` | `latest` | `latest` |
| CPU / Memory | 0.5 / 1 Gi | 0.5 / 1 Gi | **1.0 / 2 Gi** |
| Ingress | Enabled | Enabled | Enabled |
| Ingress traffic | Accepting traffic from anywhere | same | same |
| **Target port** | **8000** | **8001** | **8002** |

> **ai-service needs 2 GiB.** It loads `sentence-transformers`, which pulls in PyTorch. At
> 0.5 vCPU / 1 GiB it will OOM-crash on the first embedding request. This is also why its
> image is large (~2–3 GB) and its first cold start is slow.

> **Target port must match the Dockerfile.** Each service runs uvicorn on a different port
> (8000/8001/8002). A mismatched target port produces a container that starts fine but returns
> 502 on every request.

### Environment variables

For each app: **Containers → Edit and deploy → Container → Environment variables**. Use the
values from Steps 2–4, with these deployment-specific overrides:

**gateway**
```
ENV=PROD
CHAT_SERVICE=https://chat-service.<env-id>.<region>.azurecontainerapps.io
```

**chat-service**
```
ENV=PROD
AZURE_STORAGE_ACCOUNT_NAME=...
AZURE_STORAGE_ACCOUNT_KEY=...
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_STORAGE_CONTAINER_NAME=uploads
AI_SERVICE_URL=https://ai-service.<env-id>.<region>.azurecontainerapps.io
```

**ai-service**
```
ENV=PROD
AZURE_SEARCH_ENDPOINT=...
AZURE_SEARCH_KEY=...
AZURE_SEARCH_INDEX=documents
EMBEDDING_DIMENSION=384
LLM_PROVIDER=github
LLM_MODEL=openai/gpt-4o-mini
MODEL_TOKEN=...
```

Deploy **ai-service first**, copy its URL into chat-service, then deploy gateway last — each
depends on the one before it.

> Secrets typed here are visible to anyone with portal access to the resource group. For a
> hardened setup, store them as **Container App secrets** (Settings → Secrets) and reference
> them from the env var, or move to Key Vault with a managed identity.

### Scale-to-zero

**Settings → Scale → Min replicas = 0** keeps you inside the free grant while idle, at the cost
of a cold start on the first request. For ai-service the cold start is genuinely slow (model
load); set **Min replicas = 1** for that one if the latency bothers you — but that consumes the
free grant continuously, so watch the credit.

---

## Step 9 — Frontend on Static Web Apps

`.github/workflows/azure-static-web-apps-ashy-smoke-064d11500.yml` already exists, so a Static
Web App was created at some point. Either reuse it or create a fresh one:

**Portal → Static Web Apps → Create**

| Field | Value |
|---|---|
| Resource group | `chatgpt-clone-rg` |
| Name | `chatgpt-clone-web` |
| Plan type | **Free** |
| Source | GitHub → authorize → your repo, branch `main` |
| Build preset | **Next.js** |
| App location | `/frontend` |
| Output location | *(leave empty)* |

Creating it through the portal writes a *new* workflow file into the repo and stores the
deployment token as a secret automatically.

### Point the frontend at the backend

The existing workflow reads `NEXT_PUBLIC_API_URL` from a repo **variable** (not a secret):

**GitHub repo → Settings → Secrets and variables → Actions → Variables tab → New variable**

```
NEXT_PUBLIC_API_URL = https://chat-service.<env-id>.<region>.azurecontainerapps.io
```

Point it at **chat-service**, per the note at the top of this document. `NEXT_PUBLIC_*` values
are baked in at build time, so changing it requires re-running the workflow — not just a restart.

---

## Verification checklist

1. `GET https://ai-service.../docs` returns the Swagger UI
2. `GET https://chat-service.../docs` returns the Swagger UI
3. Upload a PDF through the frontend → a blob appears in the `uploads` container
4. **AI Search → Indexes** shows a `documents` index with a non-zero document count
5. Ask a question about the uploaded document and get a grounded answer

If step 5 fails but 1–4 pass, check ai-service logs (**Monitoring → Log stream**) — it is almost
always an expired or wrongly-scoped `MODEL_TOKEN`.

---

## Teardown

Delete the **resource group** to remove everything at once. Do this when you stop working on the
project — ACR Basic bills ~$5/month whether or not you use it.

---

## Known gaps

Things that are genuinely incomplete in the code, independent of Azure setup:

- **The gateway is bypassed.** The frontend calls chat-service directly. The gateway proxies to
  chat-service but nothing routes through it.
- **`MONGODB_URI` is unused.** It is defined in gateway and ai-service settings but no Mongo
  client exists. It now defaults to empty so the services boot; wire up a real database when you
  write the persistence layer.
- **`AzureOpenAIProvider` is an empty stub.** `generate()` is `...`. Only `github` and `ollama`
  are usable providers.
- **Streaming is not implemented.** `GithubLLMProvider.stream()` raises `NotImplementedError`.
- **CORS is wide open.** chat-service and ai-service both set `allow_origins=["*"]`. Restrict to
  the Static Web App origin before this is public.
