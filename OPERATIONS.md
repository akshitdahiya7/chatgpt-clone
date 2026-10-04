# Operations Guide

**Live site:** https://akshit-rag.duckdns.org

---

## Where do I type this?

Every command below is marked. This is the single most common mistake.

| Mark | Where | How you know |
|---|---|---|
| 💻 | **Your laptop** — PowerShell | Prompt reads `PS C:\...>` |
| ☁️ | **The server** — SSH | Prompt reads `[ec2-user@ip-172-31-23-92 ...]$` |

To leave the server and get back to your laptop: type `exit`.

---

## How it works

### The problem RAG solves

A language model only knows what it was trained on. It has never seen your CV.
You could paste the whole document into every question, but that is slow, costs
more with every message, and stops working once documents get long.

RAG (Retrieval-Augmented Generation) fixes this by **searching first, then
asking**. Only the handful of passages that actually relate to the question get
sent to the model.

### Turning text into something searchable

Ordinary search matches words. That fails here: ask *"what frameworks does he
use"* and a keyword search finds nothing, because the CV says *"Tools &
Frameworks: NumPy, Pandas..."* without the word "use".

So instead each passage is converted into an **embedding** — a list of 1536
numbers describing its meaning. Passages about similar things end up with
similar numbers, whatever words they use. The question is converted the same
way, and the closest passages win.

"Closeness" is **cosine similarity**: the angle between two of those number
lists. 1.0 means identical meaning, 0 means unrelated. Both vector databases
here report it rescaled to 0–1, where 0.5 is "unrelated".

### The pipeline, step by step

**When you upload a PDF:**

| Step | What happens | Why |
|---|---|---|
| 1 | chat-service puts the file in S3 | Keeps large files out of the services, and gives ai-service a URL to read |
| 2 | ai-service extracts the text | PyMuPDF. A scanned PDF has no text layer, and the upload is rejected with a clear message |
| 3 | The text is **chunked** into ~1000-character pieces | A whole document is too big to embed meaningfully. Chunks cut at paragraph or sentence boundaries so sentences are not sliced in half |
| 4 | Each chunk becomes an embedding | Sent to OpenAI in one batched request, not one request per chunk |
| 5 | Chunks and vectors are stored in Qdrant | Tagged with who uploaded them and which document they came from |

**When you ask a question:**

| Step | What happens | Why |
|---|---|---|
| 1 | The question becomes an embedding | So it can be compared against chunks |
| 2 | Qdrant returns the closest chunks | Filtered to your documents only |
| 3 | Very poor matches are dropped | Anything scoring below 0.5 points away from the question |
| 4 | Chunks + question become a prompt | The system prompt says: answer **only** from this context |
| 5 | GPT-4o-mini answers, streaming | Words appear as they are generated instead of after a 3-second wait |

### Why three backend services

| Service | Job |
|---|---|
| **chat-service** | Handles the browser: receives uploads, stores files, talks to ai-service |
| **ai-service** | Everything AI: chunking, embeddings, search, prompting, the model |
| **gateway** | A thin entry point. Currently deployed but unused |

The split means the AI work can change — a different model, a different vector
database — without touching the upload path. In practice that paid off: the
vector database was swapped from OpenSearch to Qdrant without a single change
to chat-service.

### Decisions worth being able to defend

**Documents are identified by a hash of their text, not a random id.**
Upload the same CV three times and you get one copy, because the hash is the
same. Before this, three uploads produced three copies, and a search returning
5 results gave only 2 distinct passages — the rest were duplicates eating the
context.

**The model decides relevance, not a score cutoff.**
The original design dropped any chunk scoring below 0.58. That blocked genuine
questions: *"what is this document about"* scores only 0.62 and *"what does it
say"* 0.57, because a question *about* a document shares little vocabulary with
its contents. Testing showed the model already refuses correctly when given
irrelevant text, so the cutoff sits at 0.5 — just enough to drop passages
pointing the wrong way — and the model does the judging.

**Every search is filtered by user, and by document when files are attached.**
Attach a file and the question is answered from that file alone. Ask without
attaching and it searches everything you have uploaded.

**One domain serves both the app and the API.**
Browsers block an HTTPS page from calling a plain HTTP address, which would
have broken a frontend hosted separately from the API. Caddy serves both from
`akshit-rag.duckdns.org`, so the problem cannot arise — and there is no CORS
configuration to get wrong.

**Qdrant instead of AWS OpenSearch.**
OpenSearch cost about $26/month and, unlike a server, could not be paused — it
billed until deleted. Qdrant's free tier has no expiry. Both providers are still
in the code; one line of config switches between them.

### The shape of it

```
Browser → Caddy (HTTPS, one domain)
            ├── /api/*  → chat-service → S3 (uploaded files)
            │                   ↓
            │              ai-service ──→ Qdrant (vectors)
            │                        └──→ OpenAI (embeddings + answers)
            └── /*      → frontend (Next.js)
```

Five Docker containers on one EC2 instance. **Only Caddy is reachable from the
internet** — the others talk to each other on a private Docker network, so the
service holding the OpenAI key is not exposed at all.

### Where the time goes

A question takes roughly 3 seconds:

| Stage | Time |
|---|---|
| Turning the question into an embedding | ~0.5s |
| Searching the vector database | ~0.4s |
| **The model writing the answer** | **~2s** |

The model dominates, which is why the answer streams: you see the first words
in about a second rather than staring at a spinner for three.

---

# 1. Run it on your laptop

**First time only** — create the config files:

💻
```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone
```
💻
```powershell
Copy-Item ai-service\.env.example ai-service\.env
```
💻
```powershell
Copy-Item chat-service\.env.example chat-service\.env
```
💻
```powershell
Copy-Item gateway\.env.example gateway\.env
```

Then fill in your keys in each file.

**Start the backend** (needs Docker Desktop running):

💻
```powershell
docker compose up -d --build
```

**Start the frontend:**

💻
```powershell
cd frontend
```
💻
```powershell
npm run dev
```

Open **http://localhost:3000**

**Stop everything:**

💻
```powershell
docker compose down
```

`Ctrl+C` in the frontend window.

---

# 2. Deploy a change

### Step 1 — push the code

💻
```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone
```
💻
```powershell
git add -A
```
💻
```powershell
git commit -m "what you changed"
```
💻
```powershell
git push
```

GitHub now builds the four Docker images automatically. Takes about 3 minutes.
Watch it at https://github.com/akshitdahiya7/chatgpt-clone/actions

### Step 2 — connect to the server

💻
```powershell
ssh -i C:\Coding\Projects\chatgpt-clone-key.pem ec2-user@34.235.183.74
```

> **If this hangs or is refused**, your home internet changed its IP address.
> Jump to [SSH is refused](#ssh-is-refused).

### Step 3 — pull and restart

☁️
```bash
cd ~/chatgpt-clone
```
☁️
```bash
git pull
```
☁️
```bash
aws ecr get-login-password --region us-east-1 | docker login -u AWS --password-stdin 020200817217.dkr.ecr.us-east-1.amazonaws.com
```
☁️
```bash
docker compose -f docker-compose.ec2.yml pull
```
☁️
```bash
docker compose -f docker-compose.ec2.yml up -d
```
☁️
```bash
docker compose -f docker-compose.ec2.yml ps
```

All five should say `running`. Done.

### If you changed a `.env` file

Copy it up from your laptop:

💻
```powershell
.\scripts\copy-env-to-ec2.ps1 -HostIp 34.235.183.74
```

Then force the container to re-read it — a normal restart will **not** pick up
config changes:

☁️
```bash
docker compose -f docker-compose.ec2.yml up -d --force-recreate ai-service
```

Check it worked:

☁️
```bash
docker compose -f docker-compose.ec2.yml exec ai-service env | grep VECTOR_STORE
```

---

# 3. Before a demo

The server costs money while it runs, so keep it stopped between demos.

### Stop it

AWS Console → **EC2** → **Instances** → select `chatgpt-clone` →
**Instance state** → **Stop instance**

### Start it

Same menu → **Start instance**. Wait for **2/2 checks passed** (~2 minutes).

Everything restarts by itself. No commands needed.

### Check it is live

💻
```powershell
curl -I https://akshit-rag.duckdns.org
```

Expect `HTTP/2 200`.

### 15 minutes before the interview

1. Start the instance
2. Open https://akshit-rag.duckdns.org
3. Upload a PDF
4. Ask one question and watch the answer stream in

If all four work, you are ready.

> **Use a PDF with real text**, not a scan or photo. A scanned PDF has no text
> layer, and the app will tell you so.

---

# 4. When something breaks

### SSH is refused

Your home IP changed, and the firewall only allows one address.

💻
```powershell
cd chat-service
```
💻
```powershell
uv run python scripts/check_ec2.py
```

It prints your current IP and flags the stale rule. Fix it:

AWS Console → **EC2** → **Security Groups** → `chatgpt-clone-security-group` →
**Edit inbound rules** → the SSH row → **Source** → **My IP** → **Save**

### The site will not load

☁️
```bash
docker compose -f docker-compose.ec2.yml ps
```

Anything not `running`, read its log:

☁️
```bash
docker compose -f docker-compose.ec2.yml logs --tail 40 ai-service
```

Usually a missing value in a `.env` file. The error says which one.

### Certificate or HTTPS errors

☁️
```bash
docker compose -f docker-compose.ec2.yml logs --tail 30 caddy
```

Look for `certificate obtained successfully`. If not:

- Ports **80 and 443** must be open in the security group (80 is required)
- `akshit-rag.duckdns.org` must point at `34.235.183.74` — check at duckdns.org

### "No readable text found"

Your PDF is a scanned image. There is no text to extract. Use a normal PDF.

Check any file first:

💻
```powershell
cd ai-service
```
💻
```powershell
uv run python -c "from app.document.factory import DocumentFactory; p=r'C:\path\to\file.pdf'; print(sum(len(x.text) for x in DocumentFactory.get_reader(p).read(p)), 'chars')"
```

`0 chars` means it is a scan.

### Answers look wrong

💻
```powershell
cd ai-service
```
💻
```powershell
uv run python scripts/profile_rag.py
```

Shows which documents are indexed, which chunks were retrieved, their scores,
and how long each step took.

### Config change did nothing

The container is still running with the old values. Use `--force-recreate`
(see [Step 3](#if-you-changed-a-env-file)).

---

# 5. Checking things work

Run from the folder shown. Each prints plain pass/fail.

| Command | Folder | Checks |
|---|---|---|
| `uv run python scripts/verify_vectordb.py` | `ai-service` | Qdrant: store, search, ranking, filters |
| `uv run python scripts/profile_rag.py` | `ai-service` | Indexed documents + query timing |
| `uv run python scripts/verify_s3.py` | `chat-service` | S3 upload and secure download links |
| `uv run python scripts/check_ec2.py` | `chat-service` | Server state and firewall rules |
| `uv run python scripts/push_to_ecr.py` | `chat-service` | What images are built |

---

# 6. Swapping parts out

Each part is chosen by one line in a `.env` file. The alternatives are still in
the code.

| What | Setting | Choices |
|---|---|---|
| Vector database | `VECTOR_STORE_PROVIDER` | `qdrant` · `opensearch` |
| Embeddings | `EMBEDDING_PROVIDER` | `openai` · `huggingface` |
| Answer model | `LLM_PROVIDER` | `openai` · `ollama` |

Change the line, copy the file up, force-recreate the container.

> **Changing the embedding model changes the vector size**, which cannot change
> after an index exists. You would need to recreate the index and re-upload
> every document.

---

# 7. What it costs

| | Running | Stopped |
|---|---|---|
| EC2 server | ~$15/mo | ~$1.30/mo |
| Fixed IP address | ~$3.60/mo | ~$3.60/mo |
| S3 + image storage | ~$1.30/mo | ~$1.30/mo |
| Qdrant | free | free |
| **Total** | **~$20/mo** | **~$6/mo** |

Plus about $0.001 per question to OpenAI.

You have **$100 of AWS credit expiring 13 March 2027**. Stopping the instance
between demos means the credit outlasts that date and your card is never
charged.

---

# 8. Shutting it all down

Do these in order. The first two are the ones that cost money.

1. **Terminate the EC2 instance** — EC2 → Instances → Instance state → **Terminate**
2. **Release the fixed IP** — EC2 → Elastic IPs → Actions → **Release**
   *(it keeps charging even with no server attached)*
3. **Empty, then delete the S3 bucket**
4. **Delete the four ECR repositories**
5. **Delete the IAM access keys** — IAM → `chatgpt-clone-dev` → Security credentials
6. **Check the bill the next day** — Billing → forecast should be ~$0

Qdrant and DuckDNS are free. Leave them.

---

# Cheat sheet

**Laptop**
```powershell
docker compose up -d --build       # run locally
docker compose down                # stop
git add -A; git commit -m "x"; git push     # deploy
ssh -i C:\Coding\Projects\chatgpt-clone-key.pem ec2-user@34.235.183.74
```

**Server**
```bash
cd ~/chatgpt-clone
git pull
docker compose -f docker-compose.ec2.yml pull
docker compose -f docker-compose.ec2.yml up -d
docker compose -f docker-compose.ec2.yml ps
docker compose -f docker-compose.ec2.yml logs --tail 40 ai-service
```
