# Operations Guide

**Live site:** https://akshit-rag.duckdns.org

---

## Read this first: the two machines

There are **two different computers**, and commands for one will not work on the
other. Every task below tells you which one you are on.

### Machine A — your laptop

- You open **PowerShell** (Start menu → type "PowerShell")
- Your prompt looks like: `PS C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone>`
- Commands use Windows paths: `C:\Coding\...`
- ⚠️ `&&` does **not** work here. Run one command per line.

### Machine B — the server (EC2)

- You reach it by typing an `ssh` command **from Machine A**
- Your prompt changes to: `[ec2-user@ip-172-31-23-92 ~]$`
- Commands use Linux paths: `~/chatgpt-clone`
- To go back to Machine A, type `exit`

### How to tell where you are

**Look at the start of your prompt line.**

| If the line starts with | You are on | Run commands marked |
|---|---|---|
| `PS C:\...>` | Machine A — laptop | **LAPTOP** |
| `[ec2-user@ip-...]$` | Machine B — server | **SERVER** |

---

# Task 1 — Run it on your laptop

**Entirely on Machine A. You never connect to the server for this.**

### Before you start

Docker Desktop must be running. Open it from the Start menu and wait until it
says "Engine running".

### Step 1 — open PowerShell and go to the project

**LAPTOP**
```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone
```

### Step 2 — create the config files

**Only the first time.** Skip to Step 4 if `ai-service\.env` already exists.

**LAPTOP**
```powershell
Copy-Item ai-service\.env.example ai-service\.env
```
**LAPTOP**
```powershell
Copy-Item chat-service\.env.example chat-service\.env
```
**LAPTOP**
```powershell
Copy-Item gateway\.env.example gateway\.env
```

### Step 3 — fill in your keys

Open each new `.env` file in your editor and replace the placeholder values
(OpenAI key, Qdrant URL and key, AWS keys, S3 bucket name).

### Step 3b — generate the session secret

This signs visitors' session cookies. The shipped value is a placeholder, and
leaving it means anyone could forge a session and read other people's
documents.

**LAPTOP**
```powershell
cd gateway
```
**LAPTOP**
```powershell
uv run python scripts/set_session_secret.py
```
**LAPTOP**
```powershell
cd ..
```

It writes a random value straight into the gateway's config file and
deliberately does not print it, so the secret never appears in your terminal
history.

> **IF you ever need to replace it**, add `--force`. Doing so signs every
> visitor out, which is exactly what you want if the value has leaked.

### Step 4 — start the backend

**LAPTOP**
```powershell
docker compose up -d --build
```

Wait about 30 seconds the first time.

### Step 5 — start the frontend

**LAPTOP**
```powershell
cd frontend
```
**LAPTOP**
```powershell
npm run dev
```

Leave this window open. The frontend runs until you press `Ctrl+C`.

### Step 6 — open it

http://localhost:3000

### When you are finished

Press `Ctrl+C` in the frontend window, then:

**LAPTOP**
```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone
```
**LAPTOP**
```powershell
docker compose down
```

---

# Task 2 — Deploy a change to the live site

**This task uses both machines.** Part A is on your laptop, Part B is on the
server. Step 4 is where you switch.

---

## Part A — on your laptop

### Step 1 — go to the project

**LAPTOP**
```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone
```

### Step 2 — push your code

**LAPTOP**
```powershell
git add -A
```
**LAPTOP**
```powershell
git commit -m "describe what you changed"
```
**LAPTOP**
```powershell
git push
```

### Step 3 — wait for the build

Pushing starts an automatic build of the four Docker images. It takes about
3 minutes.

Check it here: https://github.com/akshitdahiya7/chatgpt-clone/actions

**Wait for a green tick before continuing.** If you continue early, the server
will pull the previous version.

> **IF you also changed a `.env` file**, copy it to the server now, before
> moving on:
>
> **LAPTOP**
> ```powershell
> .\scripts\copy-env-to-ec2.ps1 -HostIp 34.235.183.74
> ```
>
> Config files are deliberately not stored in git, so `git pull` on the server
> will not bring them across.

### Step 4 — connect to the server

**LAPTOP**
```powershell
ssh -i C:\Coding\Projects\chatgpt-clone-key.pem ec2-user@34.235.183.74
```

**Your prompt should now read `[ec2-user@ip-172-31-23-92 ~]$`.**
If it does, you are on Machine B. Continue to Part B.

> **IF the connection hangs, or says "Connection timed out"**, your home
> internet changed its IP address and the firewall is blocking you.
> Go to [Problem 1](#problem-1--ssh-hangs-or-is-refused), fix it, then return
> to this step.

---

## Part B — on the server

**Every command from here runs on Machine B. Check your prompt starts with
`[ec2-user@`.**

### Step 5 — go to the project

**SERVER**
```bash
cd ~/chatgpt-clone
```

### Step 6 — get the new code

**SERVER**
```bash
git pull
```

### Step 7 — download the new images

**SERVER**
```bash
docker compose -f docker-compose.ec2.yml pull
```

> **IF this fails with "no basic auth credentials" or "denied"**, your image
> registry login expired. It lasts 12 hours. Run this, then repeat Step 7:
>
> **SERVER**
> ```bash
> aws ecr get-login-password --region us-east-1 | docker login -u AWS --password-stdin 020200817217.dkr.ecr.us-east-1.amazonaws.com
> ```

### Step 8 — restart with the new images

**SERVER**
```bash
docker compose -f docker-compose.ec2.yml up -d
```

> **IF you copied a `.env` file in Step 3**, a normal restart will not pick up
> the change. You must force it:
>
> **SERVER**
> ```bash
> docker compose -f docker-compose.ec2.yml up -d --force-recreate ai-service
> ```
>
> Then confirm the container actually received the new value:
>
> **SERVER**
> ```bash
> docker compose -f docker-compose.ec2.yml exec ai-service env | grep VECTOR_STORE
> ```

### Step 9 — check all five are running

**SERVER**
```bash
docker compose -f docker-compose.ec2.yml ps
```

All five must say `running`: `caddy`, `gateway`, `chat-service`,
`ai-service`, `frontend`.

> **IF any says `exited` or `restarting`**, read its log and go to
> [Problem 2](#problem-2--a-container-will-not-start):
>
> **SERVER**
> ```bash
> docker compose -f docker-compose.ec2.yml logs --tail 40 ai-service
> ```

### Step 10 — leave the server

**SERVER**
```bash
exit
```

Your prompt returns to `PS C:\...>`. You are back on Machine A.

### Step 11 — confirm the site works

**LAPTOP**
```powershell
curl -I https://akshit-rag.duckdns.org
```

Expect `HTTP/2 200`. Deployment complete.

---

# Task 3 — Demo the project

## To start the server

**No commands. Use the AWS website on your laptop.**

1. Open https://console.aws.amazon.com
2. Search for **EC2** and open it
3. Click **Instances** in the left menu
4. Tick the box next to **chatgpt-clone**
5. Click **Instance state** → **Start instance**
6. Wait until **Status check** reads **2/2 checks passed** — about 2 minutes

All five containers restart by themselves. There is nothing to type.

### Confirm it is live

**LAPTOP**
```powershell
curl -I https://akshit-rag.duckdns.org
```

> **IF you get `HTTP/2 200`**, you are ready.
>
> **IF the command fails or hangs**, wait another minute and try again. The
> containers take a little longer than the instance itself.

## 15 minutes before an interview

1. Start the instance (above)
2. Open https://akshit-rag.duckdns.org in a browser
3. Upload a PDF **that contains real text** — not a scan or a photo
4. Ask one question and watch the answer stream in

If all four work, you are ready.

## To stop the server afterwards

1. AWS Console → **EC2** → **Instances**
2. Tick **chatgpt-clone**
3. **Instance state** → **Stop instance**

This cuts the cost from about $15/month to about $1.30/month. **Do this every
time you finish.**

---

# Problems and fixes

## Problem 1 — SSH hangs or is refused

**Cause:** your home internet changed its IP address. The server's firewall
only allows the one address you set up with.

### Step 1 — find your current address

**LAPTOP**
```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone\chat-service
```
**LAPTOP**
```powershell
uv run python scripts/check_ec2.py
```

It prints your current IP and marks the stale rule with
`does NOT match this machine`.

### Step 2 — update the firewall

**On the AWS website, on your laptop:**

1. AWS Console → **EC2** → **Security Groups**
2. Click **chatgpt-clone-security-group**
3. **Inbound rules** tab → **Edit inbound rules**
4. Find the row where Type is **SSH**
5. Change **Source** to **My IP** — it fills in your new address
6. **Save rules**

### Step 3 — try again

Return to whichever step sent you here. SSH should now connect.

---

## Problem 2 — a container will not start

### Step 1 — see which one

**SERVER**
```bash
docker compose -f docker-compose.ec2.yml ps
```

### Step 2 — read its log

Replace `ai-service` with whichever container failed.

**SERVER**
```bash
docker compose -f docker-compose.ec2.yml logs --tail 40 ai-service
```

### Step 3 — match the error

> **IF the log says `QDRANT_URL is required`** (or any other `... is required`),
> that value is missing from the container's `.env`. Fix it on your laptop,
> copy it up, and force-recreate:
>
> **LAPTOP**
> ```powershell
> .\scripts\copy-env-to-ec2.ps1 -HostIp 34.235.183.74
> ```
> **SERVER**
> ```bash
> docker compose -f docker-compose.ec2.yml up -d --force-recreate ai-service
> ```

> **IF the log says `All connection attempts failed`**, another container is
> still starting. Wait 30 seconds and check again — it usually resolves itself.

---

## Problem 3 — the site will not load in a browser

### Step 1 — is the server even on?

AWS Console → EC2 → Instances. If the state is **stopped**, start it
(see [Task 3](#task-3--demo-the-project)).

### Step 2 — check the certificate

**SERVER**
```bash
docker compose -f docker-compose.ec2.yml logs --tail 30 caddy
```

> **IF you see `certificate obtained successfully`**, HTTPS is fine. The
> problem is elsewhere — go to Problem 2.

> **IF you see certificate errors**, check both:
> - Ports **80 and 443** are open in the security group. Port 80 is required
>   even though the site uses 443.
> - The domain still points at the server:
>
>   **LAPTOP**
>   ```powershell
>   nslookup akshit-rag.duckdns.org
>   ```
>   It must return `34.235.183.74`. If not, fix it at https://www.duckdns.org

---

## Problem 4 — "No readable text found" when uploading

**Cause:** the PDF is a scanned image or a photo. There is no text inside it to
read, only a picture of text.

**Fix:** use a PDF that was created from a document rather than scanned. If you
select text in the PDF with your mouse and nothing highlights, it is a scan.

### To check a file before uploading

**LAPTOP**
```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone\ai-service
```
**LAPTOP**
```powershell
uv run python -c "from app.document.factory import DocumentFactory; p=r'C:\path\to\your.pdf'; print(sum(len(x.text) for x in DocumentFactory.get_reader(p).read(p)), 'chars')"
```

> **IF it prints `0 chars`**, it is a scan and cannot be used.

---

## Problem 5 — "Too many requests"

**Cause:** the gateway allows 20 questions per hour per visitor, so nobody can
run up the OpenAI bill.

> **IF it is you hitting it while testing**, clearing your browser cookies
> gives you a fresh session and a fresh allowance.

> **IF you want a different limit**, change `RATE_LIMIT_REQUESTS` in the
> gateway's config file, copy it to the server, and force-recreate:
>
> **LAPTOP**
> ```powershell
> .\scripts\copy-env-to-ec2.ps1 -HostIp 34.235.183.74
> ```
> **SERVER**
> ```bash
> docker compose -f docker-compose.ec2.yml up -d --force-recreate gateway
> ```

The count is held in memory, so restarting the gateway also clears it.

---

## Problem 6 — the answers look wrong

### Step 1 — see what is actually stored and retrieved

**LAPTOP**
```powershell
cd C:\Coding\Projects\Chatgpt_Clone\chatgpt-clone\ai-service
```
**LAPTOP**
```powershell
uv run python scripts/profile_rag.py
```

This prints which documents are indexed, which passages the question matched,
their scores, and how long each stage took.

### Step 2 — match the symptom

> **IF it says "I don't have enough information" for a question the document
> can answer**, the passages scored too low. Look at the scores printed above.
> You can lower `RAG_MIN_SCORE` in `ai-service\.env`, though the usual cause is
> that the document simply does not contain the answer.

> **IF the same document appears several times**, something is wrong — document
> identity is a hash of the text, so re-uploading should replace rather than
> duplicate.

> **IF no documents are listed at all**, nothing has been uploaded to this
> vector database yet. Upload a PDF through the site.

---

# How it works

### The problem being solved

A language model only knows what it was trained on. It has never seen your CV.
You could paste the whole document into every question, but that is slow, costs
more with every message, and stops working once documents get long.

RAG (Retrieval-Augmented Generation) **searches first, then asks**. Only the
few passages that relate to the question are sent to the model.

### Why not ordinary search

Keyword search fails here. Ask *"what frameworks does he use"* and nothing
matches, because the CV says *"Tools & Frameworks: NumPy, Pandas..."* without
the word "use".

So each passage is converted into an **embedding** — a list of 1536 numbers
describing its meaning. Passages about similar things get similar numbers,
whatever words they use. The question is converted the same way, and the closest
passages win.

"Closest" means **cosine similarity**: the angle between two of those number
lists. Both vector databases here report it on a 0–1 scale, where 0.5 means
unrelated.

### When you upload a PDF

| Step | What happens | Why |
|---|---|---|
| 1 | chat-service puts the file in S3 | Keeps large files out of the services and gives ai-service a URL to read |
| 2 | ai-service extracts the text | A scanned PDF has no text layer, so the upload is rejected with a clear message |
| 3 | The text is split into ~1000-character chunks | A whole document is too big to embed meaningfully. Chunks break at paragraphs or sentences so text is not cut mid-word |
| 4 | Each chunk becomes an embedding | Sent to OpenAI in one batched request, not one per chunk |
| 5 | Chunks and vectors are stored in Qdrant | Tagged with who uploaded them and which document they came from |

### When you ask a question

| Step | What happens | Why |
|---|---|---|
| 1 | The question becomes an embedding | So it can be compared against chunks |
| 2 | Qdrant returns the closest chunks | Filtered to your documents only |
| 3 | Very poor matches are dropped | Anything below 0.5 points away from the question |
| 4 | Chunks + question become a prompt | The system prompt says: answer **only** from this context |
| 5 | GPT-4o-mini answers, streaming | Words appear as generated instead of after a 3-second wait |

### Why three backend services

| Service | Job |
|---|---|
| **chat-service** | Handles the browser: receives uploads, stores files, calls ai-service |
| **ai-service** | All the AI work: chunking, embeddings, search, prompting, the model |
| **gateway** | The front door: works out who the caller is and limits how often they can ask |

The split means the AI side can change without touching the upload path. That
paid off in practice: the vector database was swapped from OpenSearch to Qdrant
without a single change to chat-service.

### Who is asking, and how often

Every request goes through the gateway first.

**Identity.** A first-time visitor has no cookie, so the gateway creates an
anonymous session and signs it. The signature means a visitor cannot edit the
cookie to read someone else's documents — a tampered cookie is treated as a
brand new visitor. That session id becomes the `user_id` used to filter every
search, so **two people using the site cannot see each other's uploads**.

Sending `Authorization: Bearer <token>` instead gives a named user, configured
as `token:user` pairs in the gateway's settings.

**Rate limiting.** 20 questions per hour per visitor, answered with `429` and a
`Retry-After` header. Without it, anyone who found the address could spend the
OpenAI key without limit.

The gateway passes the request body through untouched, so file uploads work
without it needing to understand multipart, and it streams the reply back so
answers still arrive word by word.

> This is isolation, not security. Clearing cookies gives you a fresh identity.
> That is the right trade for a demo anyone can try; a real product would put a
> login in front of it.

### Decisions worth being able to defend

**Documents are identified by a hash of their text, not a random id.**
Upload the same CV three times and you get one copy. Before this, three uploads
produced three copies, and a search returning 5 results gave only 2 distinct
passages — the rest were duplicates filling the context.

**The model judges relevance, not a score cutoff.**
The first design dropped anything scoring below 0.58. That blocked real
questions: *"what is this document about"* scores 0.62 and *"what does it say"*
0.57, because a question *about* a document shares little vocabulary with its
contents. Testing showed the model already refuses correctly when handed
irrelevant text, so the cutoff is now 0.5 — just enough to drop passages
pointing the wrong way — and the model does the judging.

**Every search is filtered by user, and by document when files are attached.**
Attach a file and the question is answered from that file alone. Ask without
attaching and it searches everything you have uploaded.

**One domain serves both the app and the API.**
Browsers block an HTTPS page from calling a plain HTTP address, which would
break a frontend hosted separately from the API. Caddy serves both from
`akshit-rag.duckdns.org`, so the problem cannot arise and there is no CORS
configuration to get wrong.

**Qdrant instead of AWS OpenSearch.**
OpenSearch cost about $26/month and could not be paused — it billed until
deleted. Qdrant's free tier has no expiry. Both are still in the code; one line
of config switches between them.

### The shape of it

```
Browser → Caddy (HTTPS, one domain)
            ├── /api/*  → gateway  (who is asking, how often)
            │                ↓
            │            chat-service → S3 (uploaded files)
            │                ↓
            │            ai-service ──→ Qdrant (vectors)
            │                      └──→ OpenAI (embeddings + answers)
            └── /*      → frontend (Next.js)
```

Five Docker containers on one EC2 server. **Only Caddy is reachable from the
internet** — the rest talk to each other on a private network, so the service
holding the OpenAI key is not exposed.

### Where the time goes

A question takes about 3 seconds:

| Stage | Time |
|---|---|
| Turning the question into an embedding | ~0.5s |
| Searching the vector database | ~0.4s |
| **The model writing the answer** | **~2s** |

The model dominates, which is why answers stream: you see the first words in
about a second instead of staring at a spinner for three.

---

# Costs

| | Server running | Server stopped |
|---|---|---|
| EC2 server | ~$15/mo | ~$1.30/mo |
| Fixed IP address | ~$3.60/mo | ~$3.60/mo |
| S3 + image storage | ~$1.30/mo | ~$1.30/mo |
| Qdrant | free | free |
| **Total** | **~$20/mo** | **~$6/mo** |

Plus roughly $0.001 per question to OpenAI.

You have **$100 of AWS credit, expiring 13 March 2027**. Stopping the server
between demos means the credit outlasts that date and your card is never
charged.

---

# Shutting it down permanently

Do these in order. The first two are what actually cost money.

**All on the AWS website, on your laptop.**

1. **Terminate the server** — EC2 → Instances → Instance state → **Terminate**
   *(Terminate, not Stop — Stop keeps charging for the disk)*
2. **Release the fixed IP** — EC2 → Elastic IPs → Actions → **Release**
   *(it keeps charging even with no server attached)*
3. **Empty, then delete the S3 bucket**
4. **Delete the four ECR repositories**
5. **Delete the IAM access keys** — IAM → `chatgpt-clone-dev` → Security credentials
6. **Check the bill the next day** — Billing → forecast should be about $0

Qdrant and DuckDNS are free. Leave them.

---

# Cheat sheet

### On your laptop (PowerShell)

```powershell
docker compose up -d --build        # run locally
docker compose down                 # stop local
git add -A
git commit -m "message"
git push                            # starts the build
ssh -i C:\Coding\Projects\chatgpt-clone-key.pem ec2-user@34.235.183.74
```

### On the server (after ssh)

```bash
cd ~/chatgpt-clone
git pull
docker compose -f docker-compose.ec2.yml pull
docker compose -f docker-compose.ec2.yml up -d
docker compose -f docker-compose.ec2.yml ps
docker compose -f docker-compose.ec2.yml logs --tail 40 ai-service
exit
```
