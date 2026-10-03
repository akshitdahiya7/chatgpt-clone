# AWS Console Setup — Click-by-Click

Every AWS resource this project needs, in the order to create them. Companion to
`AWS_IMPLEMENTATION.md`, which covers the code changes.

**Budget:** ~$45–50/month against $100 credits expiring **Mar 13 2027**.

---

## Read this first — two things that will cost you time

**1. OpenSearch takes 15–30 minutes to create.** Start Step 5 early and do Steps 6–8 while it
builds. Don't sit watching it.

**2. AWS changes its console UI often.** Field names here may shift slightly. The *values* are what
matter — if a label doesn't match, look for the nearest equivalent rather than assuming you're in
the wrong place.

## Order

| Step | Resource | Time | Cost/mo |
|---|---|---|---|
| 1 | Budget alert | 3 min | — |
| 2 | IAM user + access keys | 5 min | — |
| 3 | ~~Bedrock~~ — **blocked on the Free Plan**, skipped | — | — |
| 4 | S3 bucket | 3 min | ~$1 |
| 5 | **OpenSearch domain** ← start early | 30 min | **~$26** |
| 6 | ECR repositories | 3 min | ~$0 |
| 7 | EC2 + key pair + Elastic IP + Docker | 20 min | ~$15 (or ~$1 stopped) |
| 8 | Amplify | 10 min | $0 |

**Set the region to `us-east-1` (N. Virginia) in the top-right selector before every step.**
Resources are region-scoped — created in the wrong region, they're invisible from the right one.
This is the single most common way to lose an hour.

---

# Step 1 — Budget alert

Do this before creating anything billable.

1. Top search bar → **Billing and Cost Management**
2. Left nav → **Budgets**
3. **Create budget**
4. Budget setup: **Use a template (simplified)**
5. Template: **Monthly cost budget**
6. Budget name: `chatgpt-clone-monthly`
7. **Enter your budgeted amount: `50`**
8. Email recipients: your email
9. **Create budget**

### Also enable free-tier alerts

1. Left nav → **Billing preferences**
2. Under **Alert preferences** → check **Receive AWS Free Tier alerts**
3. **Save preferences**

> Cost data lags ~24 hours, and a new account shows "Unable to load" for the first day. Normal.

---

# Step 2 — IAM user and access keys

Never use root credentials in application code.

## 2.1 Create the user

1. Search → **IAM** → left nav **Users** → **Create user**
2. User name: `chatgpt-clone-dev`
3. **Leave "Provide user access to the AWS Management Console" UNCHECKED** — this is a
   programmatic-only user
4. **Next**
5. Permissions options → **Attach policies directly**
6. Search for and tick each:
   - `AmazonS3FullAccess`
   - `AmazonBedrockFullAccess`
   - `AmazonOpenSearchServiceFullAccess`
   - `AmazonEC2ContainerRegistryFullAccess`
   - `AmazonEC2FullAccess`  ← needed for Step 7
7. **Next** → **Create user**

> These policies are broader than production would allow — real deployments scope to specific
> resource ARNs. Fine for a short-lived student project, but don't describe it as best practice
> if someone asks.

## 2.2 Create access keys

1. Click the `chatgpt-clone-dev` user
2. **Security credentials** tab
3. Scroll to **Access keys** → **Create access key**
4. Use case: **Application running outside AWS**
5. **Next** → (skip the description tag) → **Create access key**
6. You now see:

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

**The secret key is shown exactly once.** Click **Download .csv file**, then paste both into your
`.env` files immediately. If you lose it, delete the key and make a new one — it cannot be
recovered.

Add to both `ai-service/.env` and `chat-service/.env`:
```
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

> `.env` is gitignored, and `.dockerignore` now keeps it out of images. Don't paste these into
> chat, screenshots, or commits. If one leaks, delete it in IAM — rotation is free and instant.

---

# Step 3 — Bedrock (no action required)

**The "Model access" page has been retired.** Serverless foundation models are now enabled
automatically in all AWS commercial regions the first time your account invokes them. There is
nothing to request and no page to visit.

Two exceptions:

| Model family | What is needed |
|---|---|
| **Anthropic** (Claude) | First-time users may have to submit **use case details** before the first call succeeds |
| **AWS Marketplace** models | Someone with Marketplace permissions must invoke once, which enables it account-wide |

Amazon's own models — **Titan Text Embeddings V2** and **Nova Lite**, the two this project uses —
need nothing at all. The first `invoke_model` call activates them.

> Choosing **Nova Lite** over Claude for Change 5 sidesteps the use-case form entirely. Switch to
> Claude later if you want better answers; it is a one-line config change.

## Still confirm the region

Models activate per region, so make sure you invoke from **us-east-1**. Calling from a region where
a model is not offered gives `ValidationException: Invalid model identifier`, which reads like a
typo rather than a region problem.

## Verify credentials and model access together

A scratchpad script does this (see the path your assistant gave you), or inline:

```powershell
cd ai-service
uv add boto3
```

```python
import boto3, json
c = boto3.client("bedrock-runtime", region_name="us-east-1")
r = c.invoke_model(
    modelId="amazon.titan-embed-text-v2:0",
    body=json.dumps({"inputText": "hi", "dimensions": 1024, "normalize": True}),
)
print(len(json.loads(r["body"].read())["embedding"]))   # 1024
```

### Reading the failures

| Error | Meaning |
|---|---|
| `...account is currently being verified` | **Account activation pending.** Not a model problem — wait up to ~2h after signup/payment setup |
| `UnrecognizedClientException` | Access key id wrong or mistyped |
| `InvalidSignatureException` | Secret key wrong |
| `IncompleteSignatureException` | The two key values are **swapped** (id is 20 chars starting `AKIA`; secret is 40) |
| `AccessDeniedException` on an Anthropic model | Use-case details not yet submitted |
| `ValidationException: Invalid model identifier` | Wrong region, or the model needs a `us.` prefix |

Run this before writing Change 3. It separates a credentials problem from a code problem, which
otherwise surfaces as a confusing error from inside your embeddings provider.

---

# Step 4 — S3 bucket

1. Search → **S3** → **Create bucket**
2. Bucket type: **General purpose**
3. **Bucket name:** `chatgpt-clone-<your-initials>` — **globally unique across all of AWS**,
   lowercase, no underscores. If taken, add digits.
4. Region: **us-east-1**
5. Object Ownership: **ACLs disabled (recommended)**
6. **Block Public Access: leave ALL FOUR boxes CHECKED**
7. Bucket Versioning: **Disable**
8. Default encryption: **SSE-S3** (the default)
9. **Create bucket**

Add to `chat-service/.env`:
```
STORAGE_PROVIDER=s3
S3_BUCKET_NAME=chatgpt-clone-<your-initials>
```

> **Block Public Access stays on.** Presigned URLs are signed requests — they work against a fully
> private bucket, which is exactly the point. Making the bucket public would throw away the access
> control you already have, and a public bucket of user uploads is a genuine liability.

---

# Step 5 — OpenSearch domain

**Start this now — creation takes 15–30 minutes.** Continue to Steps 6–8 while it builds.

⚠️ **OpenSearch has no stop or pause.** It bills ~$26/month from creation until you **delete** it.
Put a deletion reminder in your calendar before you click Create.

## 5.1 Create

1. Search → **Amazon OpenSearch Service** → **Create domain**
2. **Domain name:** `chatgpt-clone-search`
3. Domain creation method: **Standard create**
4. Templates: **Dev/test**
5. Deployment option: **Domain without standby**
6. Availability Zones: **1-AZ**
7. Engine version: latest **OpenSearch 2.x**

### Instance settings
| Field | Value |
|---|---|
| Instance family | General purpose |
| Instance type | **`t3.small.search`** |
| Number of nodes | **1** |
| Storage type | EBS gp3 |
| EBS storage size per node | **10 GiB** |
| Dedicated master nodes | **Disabled** |

### Network
- **Public access** — a VPC domain is unreachable from your laptop, which makes development
  miserable. Fine-grained access control is what secures it.

### Fine-grained access control
- **Enable fine-grained access control** ✅
- **Create master user**
  - Master username: `admin`
  - Master password: needs uppercase, lowercase, digit, and special character

Save these — they're your HTTP basic auth credentials.

### Access policy
- **Only use fine-grained access control**

### Encryption
Enabling fine-grained access control forces node-to-node encryption, encryption at rest, and
HTTPS. The console enables them automatically — leave them on.

8. **Create**

## 5.2 Collect the endpoint

Once status is **Active**, open the domain and copy **Domain endpoint (IPv4)**:

```
https://search-chatgpt-clone-search-xxxxx.us-east-1.es.amazonaws.com
```

Add to `ai-service/.env` — **strip the `https://`**, the client wants a bare host:

```
VECTOR_STORE_PROVIDER=opensearch
OPENSEARCH_HOST=search-chatgpt-clone-search-xxxxx.us-east-1.es.amazonaws.com
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=<your master password>
```

## 5.3 Verify

Open the **OpenSearch Dashboards URL** from the domain page and log in with the master user. If
the dashboard loads, your credentials and public access both work.

Or from PowerShell:
```powershell
curl -u admin:<password> https://search-chatgpt-clone-search-xxxxx.us-east-1.es.amazonaws.com
```

Returns a JSON blob with version info. `401` → wrong password. A timeout → the domain is still
building, or you selected VPC access by mistake.

---

# Step 6 — ECR repositories

1. Search → **ECR** → **Create repository**
2. Visibility: **Private**
3. Repository name: `gateway`
4. Tag immutability: **Disabled** — you need `:latest` to move between builds
5. Scan on push: your choice (off is quieter)
6. **Create**

**Repeat for `chat-service` and `ai-service`.**

Note your registry URI from any repository:
```
<account-id>.dkr.ecr.us-east-1.amazonaws.com
```

Add the account ID to GitHub secrets later (Change 7).

> Free tier is 500 MB. The ai-service image only fits **after** Change 3 removes PyTorch —
> before that it's ~3 GB and you'll pay ~$0.25/month for it. Not fatal, just know why.

---

# Step 7 — EC2

## 7.1 Key pair

1. **EC2** → left nav **Key pairs** → **Create key pair**
2. Name: `chatgpt-clone-key`
3. Type: **RSA**
4. Format: **`.pem`**
5. **Create** — it downloads once

### Windows: fix the key permissions

SSH refuses to use a key that's readable by other users. In PowerShell, from the folder holding
the `.pem`:

```powershell
icacls .\chatgpt-clone-key.pem /inheritance:r
icacls .\chatgpt-clone-key.pem /grant:r "$($env:USERNAME):R"
```

Skip this and you'll get `UNPROTECTED PRIVATE KEY FILE` and a refused connection.

## 7.2 Security group

1. **EC2** → **Security Groups** → **Create security group**
2. Name: `chatgpt-clone-sg`
3. Description: `chatgpt-clone backend`
4. Inbound rules → **Add rule** for each:

| Type | Port | Source | Why |
|---|---|---|---|
| SSH | 22 | **My IP** | admin access |
| Custom TCP | 8001 | `0.0.0.0/0` | chat-service — the only port the frontend calls |
| Custom TCP | 8000 | **My IP** | gateway, debugging only |
| Custom TCP | 8002 | **My IP** | ai-service, debugging only |

5. **Create security group**

> Only 8001 is open to the world. Leave 8000 and 8002 restricted to your IP — the frontend never
> calls them, and ai-service holds your Bedrock credentials.
>
> **"My IP" changes.** On a home connection it'll rotate; if SSH stops working, edit the rule.

## 7.3 Launch the instance

1. **EC2** → **Instances** → **Launch instances**
2. Name: `chatgpt-clone`
3. AMI: **Amazon Linux 2023**
4. Instance type: **`t3.small`**
5. Key pair: `chatgpt-clone-key`
6. Network settings → **Select existing security group** → `chatgpt-clone-sg`
7. Configure storage: **16 GiB gp3**
8. **Launch instance**

> **t3.small, not t3.micro.** t3.micro has 1 GB, and ai-service needs ~1.5 GB while it still
> carries PyTorch. After Change 3 you could downsize — but you'll also be running Postgres or
> nothing else, so 2 GB stays the safe floor.

## 7.4 Elastic IP

A stopped instance gets a **new public IP** on restart, and `NEXT_PUBLIC_API_URL` is baked into
the frontend at build time — so every restart silently breaks the deployed site.

1. **EC2** → **Elastic IPs** → **Allocate Elastic IP address** → **Allocate**
2. Select it → **Actions** → **Associate Elastic IP address**
3. Resource type: **Instance** → choose `chatgpt-clone` → **Associate**

~$3.60/month, and worth every cent for not re-deploying the frontend before a demo.

⚠️ An Elastic IP that is **allocated but not attached to a running instance still bills.** Release
it at teardown, not just the instance.

## 7.5 Install Docker

```powershell
ssh -i .\chatgpt-clone-key.pem ec2-user@<your-elastic-ip>
```

Then on the instance:

```bash
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
```

**Log out and back in** — group membership only applies to new sessions:

```bash
exit
ssh -i .\chatgpt-clone-key.pem ec2-user@<your-elastic-ip>
docker ps          # should work without sudo
```

Install the compose plugin (not bundled on AL2023):

```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version
```

## 7.6 Deploy

```bash
git clone https://github.com/Im-Shivam-Singh/chatgpt-clone.git
cd chatgpt-clone
```

Create the three `.env` files (use `nano gateway/.env` etc., or `scp` them up), then:

```bash
docker compose up -d
docker compose ps
docker compose logs -f ai-service
```

> `docker compose up` builds ai-service from source, which on a t3.small while PyTorch is still a
> dependency takes **10–20 minutes and may run out of memory.** Two options: do Change 3 first so
> the image is small, or pull prebuilt images from ECR instead of building on the box. Building
> PyTorch on a 2 GB instance is the kind of thing that fails at minute 18.

## 7.7 Stopping to save money

**Instances → select → Instance state → Stop instance.**

Stopped costs **$0 compute** — only ~$1.30/month for the EBS volume, plus the Elastic IP. A
4-hour demo session is about $0.08. With `restart: unless-stopped` in your compose file, the stack
comes back by itself on boot.

This does **not** apply to OpenSearch, which keeps billing regardless.

---

# Step 8 — Amplify (frontend)

## 8.1 Create the app

1. Search → **AWS Amplify** → **Create new app**
2. Source: **GitHub** → **Authorize** → pick `chatgpt-clone`, branch `main`
3. Amplify should auto-detect **Next.js — SSR**
4. ⚠️ **Set the app root directory to `frontend`** — under *Advanced settings* or the monorepo
   option. Without this the build fails, because `package.json` isn't at the repo root.
5. Environment variables → add:
   ```
   NEXT_PUBLIC_API_URL = http://<your-elastic-ip>:8001
   ```
6. **Save and deploy**

## 8.2 ⚠️ The mixed-content problem — read before you demo

**Amplify serves your site over HTTPS. Your EC2 backend is plain HTTP. Browsers block HTTPS pages
from calling HTTP endpoints,** so the deployed frontend will fail every API call with a console
error and no network request. CORS settings cannot fix this — it's the browser refusing before the
request leaves.

This is the most likely thing to break in the whole setup, and it is not a bug in your code.

Three fixes, cheapest first:

| Fix | Effort | Cost |
|---|---|---|
| **Run the frontend locally** against `http://<eip>:8001` | None | $0 |
| **Caddy on EC2** with a real domain — automatic Let's Encrypt TLS | ~30 min + domain | ~$1/yr domain |
| **CloudFront** in front of EC2 to terminate TLS | ~20 min | ~$0 at your volume |

For an interview, local frontend + deployed backend is a perfectly honest demo, and you can
explain the TLS gap as a known next step. If you want the fully-deployed story, Caddy is the
cleanest — you get a real HTTPS URL, and a free domain from DuckDNS works with it.

> `NEXT_PUBLIC_*` variables are **baked in at build time**, not read at runtime. Changing
> `NEXT_PUBLIC_API_URL` requires a **redeploy**, not a restart.

## 8.3 Clean up the Azure workflow

Delete `.github/workflows/azure-static-web-apps-ashy-smoke-064d11500.yml` once Amplify works —
otherwise it fails on every push and buries real failures in red noise.

---

# Verification checklist

| # | Check | Expected |
|---|---|---|
| 1 | Bedrock one-liner (Step 3) | prints `1024` |
| 2 | `curl -u admin:pass https://<opensearch-host>` | JSON version info |
| 3 | Upload a PDF via frontend | object in S3; `sas_url` downloads |
| 4 | OpenSearch → Indices | `documents`, non-zero count |
| 5 | Ask about the document | grounded answer |
| 6 | Stop then start EC2 | stack returns on its own |

---

# Teardown — in this order

Do this on your deletion date. The first two items are what actually drain credits.

1. **Delete the OpenSearch domain** — ~$26/mo, cannot be paused, the big one
   - OpenSearch → domain → **Actions → Delete**
2. **Terminate the EC2 instance** — *terminate*, not stop
   - Instance state → **Terminate instance**
3. **Release the Elastic IP** — still bills while allocated and unattached
   - Elastic IPs → select → **Actions → Release**
4. **Empty, then delete the S3 bucket** (deleting requires emptying first)
5. **Delete the three ECR repositories**
6. **Delete the Amplify app**
7. **Delete the IAM access keys** (IAM → user → Security credentials)
8. **A day later:** Billing → **Bills** → confirm the forecast is ~$0

> A forgotten OpenSearch domain and an unreleased Elastic IP are the two most common ways students
> discover their credits gone. Everything else here is cents.
