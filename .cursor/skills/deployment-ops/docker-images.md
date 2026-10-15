# Docker images — three roles

RAGStone uses **three separate images**. Do not mix runtimes for the same task (e.g. do not run `pytest` in the devops image or `terraform` in the bot-test image).

**Rebuild rule:** rebuild an image when its **baked dependency file** changes (`requirements.txt`, `pyproject.toml`, or Dockerfiles). Day-to-day **code edits** use bind mounts — no rebuild.

| Image | Dockerfile | Compose | Service name |
|-------|------------|---------|--------------|
| **Devops** | [`Dockerfile.dev`](../../../Dockerfile.dev) | [`docker-compose.dev.yml`](../../../docker-compose.dev.yml) | `dev` |
| **Bot test** | [`Dockerfile.bot`](../../../Dockerfile.bot) | [`docker-compose.bot.yml`](../../../docker-compose.bot.yml) | `bot-test` |
| **Pinecone indexer** | [`pinecone-pipeline/Dockerfile`](../../../pinecone-pipeline/Dockerfile) | [`docker-compose.pinecone.yml`](../../../docker-compose.pinecone.yml) | `pinecone-indexer` |

---

## 1. Devops (`Dockerfile.dev` → `dev`)

**Purpose:** Azure and platform operations — **not** application unit tests or corpus parsing.

| Included (baked) | Not included |
|------------------|--------------|
| Ubuntu 22.04, Python 3.11, `uv` | `teams-bot` pip packages |
| Terraform | Pinecone parser stack (3.12 / unstructured / Tesseract) |
| Azure CLI | |
| Azure Functions Core Tools v4 | |
| *(optional)* `httpx` + `msal` for `sharepoint_sync.py` — **unused by default** (human SharePoint upload per KB skill) | |

**Persistent volumes:** `azure-config` (`az login`), `terraform-plugins` (Terraform cache).

**Typical commands** (repo root; wrappers call this image):

| Use case | Entry |
|----------|--------|
| Interactive ops shell | `.\scripts\dev-shell.ps1` / `./scripts/dev-shell.sh` |
| KQL / App Insights | `./scripts/kql.sh scripts/kql/…` |
| Log snapshot | `… fetch-azure-logs.sh` |
| Terraform | `.\scripts\terraform.sh dev plan` or `scripts\terraform.cmd dev plan` |
| Deploy bot to Azure | `.\scripts\deploy.sh dev` or `scripts\deploy.cmd dev` |
| Prod deploy | `scripts\deploy.cmd prod` (on `release`) |
| Clear/query conversation tables | `clear_conversation_memory_docker.sh`, `query_conversations_table.sh`, … |
| SharePoint script (optional) | `scripts/kb.sh sharepoint` — only if user confirms Graph access; **default: human upload** (KB skill) |

**Env:** `sharepoint_sync.py` loads `/workspace/.env` (`MICROSOFT_APP_TENANT_ID`, `MICROSOFT_APP_ID`, …). Compose also passes selected keys; mounted `.env` is authoritative.

**Rebuild when:** `Dockerfile.dev` or `scripts/sharepoint_sync_requirements.txt` changes.

---

## 2. Bot test (`Dockerfile.bot` → `bot-test`)

**Purpose:** Local **Teams bot / Azure Functions Python 3.11** parity — unit tests, RAG harnesses, optional `func start`. Same runtime family as the deployed Function App (Linux, Python 3.11, same `requirements.txt`).

| Included (baked at build) | Mounted at run |
|---------------------------|----------------|
| Python 3.11 | Whole repo → `/workspace` |
| `pip install -r teams-bot/requirements.txt` | Live `teams-bot/` code |
| Azure Functions Core Tools v4 | `teams-bot/logs/`, `local.settings.json` |

**Does not include:** Terraform, Azure CLI (use **dev** image for deploy/logs).

**Typical commands:**

```bash
./scripts/bot.sh pytest tests/ -q
./scripts/bot.sh rag --file logs/client_feedback_golden.txt
./scripts/bot.sh probe "pytanie" --top-k 8
./scripts/bot.sh run func start   # optional; needs local.settings.json
```

Windows: `scripts\bot.cmd pytest tests/ -q`

**Rebuild when:** `teams-bot/requirements.txt` or `Dockerfile.bot` changes:

```bash
docker compose -f docker-compose.bot.yml build bot-test
```

---

## 3. Pinecone indexer (`pinecone-pipeline/Dockerfile` → `pinecone-indexer`)

**Purpose:** **Corpus ingest only** — parse DOCX/PDF/PPTX/XLSX, chunk, embed, upsert to Pinecone. Python **3.12** + OCR/poppler/Tesseract (not the Function App runtime).

| Included (baked at build) | Mounted at run |
|---------------------------|----------------|
| `uv sync` for pipeline (`pyproject.toml`) | `source_data/` → `/data/docs` (ro) |
| Parser / OCR system packages | `chunk_output/` → `/data/chunk_output` |

After changing `pinecone-pipeline/` **code** (not just corpus files), rebuild:

```bash
docker compose -f docker-compose.pinecone.yml build pinecone-indexer
```

**Typical commands:**

```bash
./scripts/kb.sh index
./scripts/kb.sh reindex --force "5 Instrukcje/foo.docx"
```

**Host alternative:** `cd pinecone-pipeline && uv run …` on Python ≥3.12 — same logic, not the same OCR image.

---

## Decision table

| Task | Image |
|------|--------|
| App Insights / KQL | **dev** |
| Terraform apply | **dev** |
| `deploy-fast.sh` / `deploy-full.sh` | **dev** |
| Conversation table maintenance | **dev** |
| `bot.sh pytest`, golden tests | **bot-test** |
| `bot.sh rag`, `bot.sh probe` | **bot-test** |
| `func start` (local HTTP bot) | **bot-test** |
| `kb.sh` (index / reindex / delete) | **pinecone-indexer** |
| SharePoint files | **Human upload** (KB skill); script in `dev` only if grants exist |
| Gmail scripts, git | **Host** (no image) |

---

## Related

- [SKILL.md](SKILL.md) — deploy procedure
- [workflow.md](workflow.md) — first-time setup
- [AGENTS.md](../../../AGENTS.md) — skill router
