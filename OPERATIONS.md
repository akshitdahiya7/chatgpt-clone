# Operations Guide

Everything needed to run, deploy, demo, and tear down this project.

**Live site:** https://akshit-rag.duckdns.org

---

## Contents

1. [Architecture](#1-architecture)
2. [Run locally](#2-run-locally)
3. [Deploy a change](#3-deploy-a-change)
4. [Start and stop for a demo](#4-start-and-stop-for-a-demo)
5. [Verification scripts](#5-verification-scripts)
6. [Switching providers](#6-switching-providers)
7. [Troubleshooting](#7-troubleshooting)
8. [Costs](#8-costs)
9. [Teardown](#9-teardown)

---

## 1. Architecture

```
                    https://akshit-rag.duckdns.org
                                │
                         ┌──────┴──────┐
                         │    Caddy    │  TLS, :80 :443
                         └──────┬──────┘
                 /api/*  ───────┴───────  /*
                    │                      │
            ┌───────┴──────┐      ┌────────┴───────┐
            │ chat-service │      │    frontend    │
            │    :8001     │      │  Next.js :3000 │
            └───────┬──────┘      └────────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
    ┌────┴────┐         ┌──────┴─────┐
    │   S3    │         │ ai-service │ :8002
    │ uploads │         └──────┬─────┘
    └─────────┘                │
                    ┌──────────┴──────────┐
                    │                     │
              ┌─────┴─────┐        ┌──────┴──────┐
              │  Qdrant   │        │   OpenAI    │
              │  vectors  │        │ embed + LLM │
              └───────────┘        └─────────────┘
```

**Request flow for a question with a file:**

1. Browser posts multipart to `/api/v1/chat/stream`
2. Caddy routes `/api/*` to chat-service
3. chat-service uploads the file to S3 and gets a presigned URL
4. ai-service reads the PDF, chunks it, embeds the chunks, stores them in Qdrant
5. The question is embedded and searched against Qdrant, filtered by user and document
6. Chunks scoring below `RAG_MIN_SCORE` are dropped
7. The surviving chunks become the prompt, and the answer streams back token by token

Only Caddy publishes ports. The four application containers are reachable
solely on the internal Docker network.

---

## 2. Run locally

### Prerequisites

- Docker Desktop running
- `uv` installed (`pip install uv`)
- Node 22+ for frontend development

### Configuration

Each service reads its own `.env`, which is gitignored. Copy the templates and
fill them in:

```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone
Copy-Item ai-service\.env.example   ai-service\.env
Copy-Item chat-service\.env.example chat-service\.env
Copy-Item gateway\.env.example      gateway\.env
```

### Start the backend

```powershell
docker compose up -d --build
```

```powershell
docker compose ps
```

| Service | URL |
|---|---|
| gateway | http://localhost:8000/docs |
| chat-service | http://localhost:8001/docs |
| ai-service | http://localhost:8002/docs |

### Start the frontend

```powershell
cd frontend
```
```powershell
npm install
```
```powershell
npm run dev
```

Open http://localhost:3000

### Stop

```powershell
docker compose down
```

Add `-v` to also delete volumes. Press `Ctrl+C` in the frontend window.

### Run one service without Docker

```powershell
cd ai-service
```
```powershell
uv sync
```
```powershell
uv run uvicorn app.main:app --reload --port 8002
```

---

## 3. Deploy a change

### 3.1 Push the code

```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone
```
```powershell
git add -A
```
```powershell
git commit -m "your message"
```
```powershell
git push
```

GitHub Actions then lints every service, builds four images, and pushes them to
ECR tagged with the commit SHA and `latest`.

### 3.2 Watch the build

https://github.com/akshitdahiya7/chatgpt-clone/actions

Or from the command line:

```powershell
cd chat-service
```
```powershell
uv run python scripts/push_to_ecr.py
```

That prints what is currently in ECR, including the newest tag.

### 3.3 Connect to the instance

```powershell
ssh -i C:\Coding\Projects\chatgpt-clone-key.pem ec2-user@34.235.183.74
```

> **If SSH hangs or is refused**, your home IP has changed. See
> [Troubleshooting](#71-ssh-refused-or-hangs).

### 3.4 Pull and restart

```bash
cd ~/chatgpt-clone
```
```bash
git pull
```
```bash
REG=020200817217.dkr.ecr.us-east-1.amazonaws.com
```
```bash
PW=$(aws ecr get-login-password --region us-east-1)
```
```bash
echo "$PW" | docker login -u AWS --password-stdin $REG
```
```bash
unset PW
```
```bash
docker compose -f docker-compose.ec2.yml pull
```
```bash
docker compose -f docker-compose.ec2.yml up -d
```
```bash
docker compose -f docker-compose.ec2.yml ps
```

`ECR_REGISTRY` and `DOMAIN` come from the root `.env` on the instance, so they
do not need exporting. The ECR login token expires after 12 hours, so it is
needed on each new session.

### 3.5 Changed a `.env`?

`env_file` is read when a container is **created**, so a plain `up -d` can
leave the old environment in place. Force it:

```bash
docker compose -f docker-compose.ec2.yml up -d --force-recreate ai-service
```

Confirm what the container actually received:

```bash
docker compose -f docker-compose.ec2.yml exec ai-service env | grep VECTOR_STORE
```

### 3.6 Copy local config up

From a **PowerShell window on your laptop**, not the SSH session:

```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone
```
```powershell
.\scripts\copy-env-to-ec2.ps1 -HostIp 34.235.183.74
```

---

## 4. Start and stop for a demo

A stopped instance costs **$0 compute** — about $1.30/month for its disk. Stop
it between demos.

### Stop

AWS Console → EC2 → Instances → select `chatgpt-clone` → **Instance state → Stop instance**

### Start

Same menu → **Start instance**. Wait for **2/2 checks passed**, about 2 minutes.

`restart: unless-stopped` brings all five containers back automatically. No
commands needed.

### Check it is live

```powershell
curl -I https://akshit-rag.duckdns.org
```

Expect `HTTP/2 200`.

> The Elastic IP means the address survives a stop/start. Without it the IP
> would change and the certificate would stop matching.

**Before an interview:** start the instance 15 minutes early, open the site,
upload a PDF, and ask one question to confirm the whole chain works.

---

## 5. Verification scripts

Each reads its own service's `.env` and prints only masked values.

| Script | Run from | Checks |
|---|---|---|
| `scripts/verify_vectordb.py` | `ai-service` | Vector store: create, upsert, search, ranking, score range, document and user scoping |
| `scripts/profile_rag.py` | `ai-service` | Index contents and per-stage query timing |
| `scripts/verify_s3.py` | `chat-service` | S3 upload, presigned URL, that unsigned access is blocked |
| `scripts/check_ec2.py` | `chat-service` | Instance state, IAM profile, security group rules against your current IP |
| `scripts/push_to_ecr.py` | `chat-service` | What is in ECR; `--push` uploads local images |
| `scripts/setup_ecr.py` | `chat-service` | Creates the ECR repositories (idempotent) |

```powershell
cd ai-service
```
```powershell
uv run python scripts/verify_vectordb.py
```

```powershell
cd chat-service
```
```powershell
uv run python scripts/check_ec2.py
```

---

## 6. Switching providers

Every provider is chosen by an environment variable. The alternatives stay in
the code, so switching is config only.

| Subsystem | Variable | Options |
|---|---|---|
| Vector store | `VECTOR_STORE_PROVIDER` | `qdrant` · `opensearch` |
| Embeddings | `EMBEDDING_PROVIDER` | `openai` · `huggingface` |
| LLM | `LLM_PROVIDER` | `openai` · `ollama` |
| Storage | `STORAGE_PROVIDER` | `s3` |

### Back to OpenSearch

In `ai-service/.env`:

```
VECTOR_STORE_PROVIDER=opensearch
OPENSEARCH_HOST=search-xxxx.us-east-1.es.amazonaws.com
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=...
```

Then force-recreate (§3.5). Verify with `verify_vectordb.py`, which tests
whichever provider is configured.

### Local embeddings, no API key

```powershell
cd ai-service
```
```powershell
uv sync --group local
```

Then set `EMBEDDING_PROVIDER=huggingface` and `EMBEDDING_DIMENSION=384`.

> ⚠️ **Changing the embedding model changes the vector size**, and dimensions
> are fixed when an index is created. You must recreate the index and
> re-ingest every document.

---

## 7. Troubleshooting

### 7.1 SSH refused or hangs

Home broadband rotates your IP, and the security group pins SSH to one address.

```powershell
cd chat-service
```
```powershell
uv run python scripts/check_ec2.py
```

It flags any rule that no longer matches you. Fix in **EC2 → Security Groups →
`chatgpt-clone-security-group` → Edit inbound rules → SSH → Source → My IP → Save**.

### 7.2 A container will not start

```bash
docker compose -f docker-compose.ec2.yml logs ai-service | tail -40
```

Usually a missing or malformed `.env` value. The factories raise a named error,
for example `QDRANT_URL is required`.

### 7.3 Config change had no effect

The container was not recreated. See §3.5.

### 7.4 Certificate problems

```bash
docker compose -f docker-compose.ec2.yml logs caddy | tail -30
```

Look for `certificate obtained successfully`. Common causes:

- Ports 80 and 443 not open in the security group — port 80 is required for validation
- `DOMAIN` unset or wrong — check the root `.env` on the instance
- DuckDNS not pointing at the Elastic IP — `nslookup akshit-rag.duckdns.org`

> Let's Encrypt rate-limits **failed** validations: 5 per hostname per hour.
> Read the log and fix the cause rather than retrying.

### 7.5 "No readable text found"

The PDF is a scanned image with no text layer. Extraction returns zero
characters, so there is nothing to index. Use a text-based PDF, or add OCR.

Check any file locally:

```powershell
cd ai-service
```
```powershell
uv run python -c "from app.document.factory import DocumentFactory; p=r'C:\path\to\file.pdf'; print(sum(len(x.text) for x in DocumentFactory.get_reader(p).read(p)), 'chars')"
```

### 7.6 Answers are wrong or absent

```powershell
cd ai-service
```
```powershell
uv run python scripts/profile_rag.py
```

It prints the indexed documents and the retrieved chunks with scores.

- **"I don't have enough information"** on a question that should work: scores
  are below `RAG_MIN_SCORE` (0.58). Lower it, or the document may not contain
  the answer.
- **Duplicate documents:** should be impossible, since `document_id` is a hash
  of the content. If you see duplicates, the extracted text differs between
  uploads.

### 7.7 Running out of memory

Five containers on a 2 GB instance is tight.

```bash
docker stats --no-stream
```

The gateway is deployed but nothing calls it, so it is the first thing to drop:

```bash
docker compose -f docker-compose.ec2.yml stop gateway
```

---

## 8. Costs

| Resource | Running | Stopped |
|---|---|---|
| EC2 t3.small | ~$15/mo | ~$1.30/mo (disk only) |
| Elastic IP | ~$3.60/mo | ~$3.60/mo |
| S3 | ~$1/mo | ~$1/mo |
| ECR | ~$0.30/mo | ~$0.30/mo |
| Qdrant Cloud | **free** | free |
| OpenAI | per use, about $0.001 per question | — |
| **Total** | **~$20/mo** | **~$6/mo** |

Against $100 of AWS credits expiring **13 March 2027**, stopping the instance
between demos means the credits outlast the expiry and the card is never
charged.

> **OpenSearch was ~$26/month and could not be paused.** Moving to Qdrant
> removed it.

---

## 9. Teardown

Order matters: the costly, un-pausable things first.

```powershell
cd chat-service
```
```powershell
uv run python scripts/check_ec2.py
```

1. **OpenSearch domain** — Console → OpenSearch → `chatgpt-clone-search` → Actions → Delete
2. **EC2 instance** — Instance state → **Terminate** (not Stop)
3. **Elastic IP** — Elastic IPs → select → Actions → **Release** *(an allocated but unattached IP still bills)*
4. **S3 bucket** — empty it first, then delete
5. **ECR repositories** — delete all four
6. **IAM access keys** — IAM → `chatgpt-clone-dev` → Security credentials → delete
7. **Check the bill** a day later — Billing → Bills → forecast should be ~$0

Qdrant Cloud and DuckDNS are free and can be left alone.

---

## Quick reference

```powershell
# Local
docker compose up -d --build          # start backend
docker compose ps                     # status
docker compose logs -f ai-service     # follow logs
docker compose down                   # stop
cd frontend; npm run dev              # frontend

# Deploy
git add -A; git commit -m "..."; git push
ssh -i C:\Coding\Projects\chatgpt-clone-key.pem ec2-user@34.235.183.74
```

```bash
# On the instance
cd ~/chatgpt-clone
git pull
docker compose -f docker-compose.ec2.yml pull
docker compose -f docker-compose.ec2.yml up -d
docker compose -f docker-compose.ec2.yml ps
docker compose -f docker-compose.ec2.yml logs -f caddy
```
