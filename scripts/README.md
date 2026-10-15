# Scripts

Utility scripts for development, deployment, and Azure configuration.

## SharePoint corpus mirror

**Agents:** use **`.cursor/skills/knowledge-base-curator`** — default is **human upload** to `AI/dev` or `AI/prod` (automated sync often blocked).

Optional operator script when Graph access works: `sharepoint_sync.py` — see [citation-sharepoint-links.md](../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md), [TASKS.md](../docs/TASKS.md) task **35**.

## Development Environment

### `dev-shell.sh` / `dev-shell.ps1`
Start a shell inside the Docker development container.

```bash
# Linux/Mac
./scripts/dev-shell.sh

# Windows PowerShell
.\scripts\dev-shell.ps1
```

## Agent entry scripts (one operation each)

| Skill | Script | Windows |
|-------|--------|---------|
| **knowledge-base-curator** | `./scripts/kb.sh` | `scripts\kb.cmd` |
| **bot-quality-evaluation** | `./scripts/bot.sh`, `./scripts/kql.sh` | `scripts\bot.cmd`, `scripts\kql.cmd` |
| **deployment-ops** | `./scripts/deploy.sh`, `./scripts/terraform.sh` | `scripts\deploy.cmd`, `scripts\terraform.cmd` |

### `kb.sh` — corpus / Pinecone

```bash
./scripts/kb.sh reindex "Topic/file.docx" [--force]
./scripts/kb.sh delete --source-relative-path "Topic/file.docx"
./scripts/kb.sh index
./scripts/kb.sh qa-export --seed 42
./scripts/kb.sh sharepoint --auth device --dry-run   # optional; human upload is default
```

Skill: [`.cursor/skills/knowledge-base-curator`](../.cursor/skills/knowledge-base-curator/SKILL.md).

### `bot.sh` — tests / local RAG / probe

```bash
./scripts/bot.sh pytest tests/ -q
./scripts/bot.sh rag --file logs/client_feedback_golden.txt
./scripts/bot.sh probe "pytanie" --top-k 8
```

Acceptance criteria: [`.cursor/skills/bot-quality-evaluation/acceptance-criteria.md`](../.cursor/skills/bot-quality-evaluation/acceptance-criteria.md).

### `kql.sh` — App Insights

```bash
./scripts/kql.sh -o table scripts/kql/last_rag_turn.kql
```

Full options: **`scripts/run_kql.sh --help`**, sketch index: **[`kql/README.md`](kql/README.md)**.

Optional snapshot to **`logs/`**: **`scripts/fetch-azure-logs.sh`** (see [docker-images.md](../.cursor/skills/deployment-ops/docker-images.md) § devops).

## Deployment (one entry per operation)

Agents: **`.cursor/skills/deployment-ops`**. Infrastructure spec: **[`infrastructure/README.md`](../infrastructure/README.md)**.

| Operation | Script (host, repo root) | Windows CMD |
|-----------|--------------------------|-------------|
| Terraform | `./scripts/terraform.sh <dev\|prod> <cmd>` | `scripts\terraform.cmd dev plan` |
| Bot publish | `./scripts/deploy.sh <dev\|prod> [--full] [--terraform]` | `scripts\deploy.cmd dev --terraform` |

Both run inside the **`dev`** Docker image by default. Use `--local` only when already in the container (`dev-shell`).

### Git ↔ environment sync

| Target | Branch | Meaning |
|--------|--------|---------|
| **dev** | `main` | Feature work merged to `main` and pushed before `./scripts/deploy.sh dev` |
| **prod** | `release` | `main` merged into `release` and pushed before `./scripts/deploy.sh prod` |

Prod changelog: [`docs/deployments/CHANGELOG.md`](../docs/deployments/CHANGELOG.md) — append in the same session as prod deploy; **Git** line must match `git rev-parse HEAD` on `release`.

```bash
# Dev (on main)
git checkout main && git pull origin main
./scripts/deploy.sh dev

# Infra + bot
./scripts/deploy.sh dev --terraform

# Prod (on release)
git fetch origin && git checkout release && git merge main && git push origin release
./scripts/deploy.sh prod --terraform
```

**Terraform vs bot:** `terraform apply` provisions Azure resources and app settings; it does **not** publish `teams-bot/` Python. Use `deploy.sh` (or `deploy-fast` / `deploy-full` inside the container). Details: [`infrastructure/README.md`](../infrastructure/README.md).

Confirm **`.env`** has **`DEV_AZURE_*`** / **`PROD_AZURE_*`** (or legacy **`AZURE_*`** for dev). **`az login`** once in the dev container (`azure-config` volume).

### `deploy-fast.sh` (internal / container)
Fast deployment using local build (~30 seconds).

```bash
# Inside container
./scripts/deploy-fast.sh dev      # Deploy to dev
./scripts/deploy-fast.sh prod     # Deploy to prod (only from release branch)
```

**What it does:**
1. Checks branch for prod deployments
2. Selects Terraform workspace (`default` for dev, `prod` for prod) and reads function app / resource group from state
3. Installs Python dependencies locally (cached if unchanged)
4. Uploads pre-built package to Azure
5. Syncs `PINECONE_NAMESPACE`, `PINECONE_INDEX`, and `PINECONE_INDEX_NAME` from `infrastructure/environments/<env>.tfvars` (code-only publish does not update these)
6. Restarts function app to sync triggers
7. Verifies health endpoint

**Use when:** Making code changes only (no dependency changes)

### `deploy-full.sh` (First deploy or dependency changes)
Full deployment using Azure remote build (~2 minutes).

```bash
# Inside container
./scripts/deploy-full.sh dev      # Deploy to dev
./scripts/deploy-full.sh prod     # Deploy to prod (only from release branch)
```

**What it does:**
1. Checks branch for prod deployments
2. Selects Terraform workspace and reads function app / resource group from state
3. Uploads source code to Azure
4. Azure builds dependencies remotely
5. Syncs Pinecone app settings from `environments/<env>.tfvars` (same as `deploy-fast.sh`)
6. Automatically registers function triggers

**Use when:**
- First deployment
- After changing `requirements.txt`
- If `deploy-fast.sh` fails

### Deployment Decision Table

| Scenario | Script |
|----------|--------|
| First deployment | `deploy-full.sh dev` |
| Added new dependency | `deploy-full.sh dev` |
| Updated dependency version | `deploy-full.sh dev` |
| Code changes only | `deploy-fast.sh dev` |
| Functions not registering | `deploy-full.sh dev` |
| Release to production | `git checkout release && git merge main && ./scripts/deploy.sh prod` |

## Secrets and app settings

OpenAI, Pinecone, and the bot client secret are created in **Key Vault by Terraform** and wired into the Function App (`infrastructure/keyvault.tf`, `infrastructure/functions.tf`). **`SHAREPOINT_LIBRARY_BASE_URL`** (citation links) is set from **`sharepoint_library_base_url`** in `infrastructure/environments/*.tfvars` — not by `deploy-fast.sh`. Use `.env` for `terraform apply` variables as described in `infrastructure/README.md`—do not commit API keys. Citation / SharePoint overview: [citation-sharepoint-links.md](../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md).

To verify a deployment, use `curl` on `/api/health` (see **`.cursor/skills/deployment-ops/reference.md`**).
