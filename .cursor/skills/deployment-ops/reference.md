# Deployment reference (operators + agents)

Human-oriented detail for **`deployment-ops`**. Commands: [workflow.md](workflow.md).

**Infrastructure (canonical):** [`infrastructure/README.md`](../../../infrastructure/README.md) — resource list, tfvars, tenants, outputs, destroy.

## Terraform outputs

Resource names differ per environment. After apply:

```bash
cd infrastructure && terraform output
```

Example dev stack (replace with your outputs):

| Resource | Typical output key | Purpose |
|----------|-------------------|---------|
| Resource Group | `resource_group_name` | Container |
| Function App | `function_app_name` | Bot backend |
| Bot App ID | `bot_app_id` | Teams identity |
| Key Vault | `key_vault_name` | Secrets |
| Health | `function_app_url` + `/api/health` | Smoke test |

Workspaces: **dev** = `default`, **prod** = `prod`.

## Architecture (deployed bot)

```
Teams → Azure Bot Service → Azure Functions
  → webhook ack + streaming
  → LangGraph RAG (optimizer → Pinecone → answer)
  → Azure Table Storage (memory)
```

Citations / SharePoint URLs: [citation-sharepoint-links.md](../../knowledge-base-curator/citation-sharepoint-links.md) (KB curator owns corpus mirror).

## Terraform apply vs bot code deploy

| Step | What changes |
|------|----------------|
| **`terraform apply`** | RG, Function App *resource*, plan, storage, Key Vault, App Insights, app settings / KV refs, bot channel. Does **not** publish latest `teams-bot/` source alone. |
| **`deploy-fast.sh`** | Publishes Python package; syncs `PINECONE_*` from `infrastructure/environments/<env>.tfvars`. |
| **`deploy-full.sh`** | Same + remote dependency build (~2 min). First deploy or `requirements.txt` changes. |

**Typical flows**

- New env: `terraform init` → `apply` → `deploy-full`
- Day-to-day code: `deploy-fast` only
- Prod: **`release`** branch → deploy → append [`docs/deployments/CHANGELOG.md`](../../../docs/deployments/CHANGELOG.md)

`OPENAI_*` / optimizer models: Terraform app settings. `SHAREPOINT_LIBRARY_BASE_URL`: Terraform tfvars only (not deploy-fast).

## Teams app package

Not in git. Build:

```powershell
cd teams-app
.\build-package.ps1 -BotId "<bot_app_id_from_terraform output>" -Environment dev
```

Upload `northwind-ai-<env>.zip` in [Teams Admin Center](https://admin.teams.microsoft.com).

Customer steps: [`docs/customer-support/CUSTOMER-SETUP-PL.md`](../../../docs/customer-support/CUSTOMER-SETUP-PL.md), [`CUSTOMER-SETUP-EN.md`](../../../docs/customer-support/CUSTOMER-SETUP-EN.md). User guides: [`BOT-USAGE-PL.md`](../../../docs/customer-support/BOT-USAGE-PL.md), [`BOT-USAGE-EN.md`](../../../docs/customer-support/BOT-USAGE-EN.md).

## Smoke test after deploy

1. `curl https://<function_app_host>/api/health` → `healthy`
2. Teams 1:1 — status + streamed reply + sources when RAG runs

## Logs and audits (not this skill’s procedure)

Use **`bot-quality-evaluation`** skill + [`scripts/kql/README.md`](../../../scripts/kql/README.md) (`run_kql.sh` in **`dev`** container). Do not duplicate KQL here.

## Host entrypoints (repo root)

| Operation | Linux / Git Bash | Windows CMD |
|-----------|------------------|-------------|
| Terraform | `./scripts/terraform.sh dev plan` | `scripts\terraform.cmd dev plan` |
| Deploy | `./scripts/deploy.sh dev [--terraform] [--full]` | `scripts\deploy.cmd dev --terraform` |

Branch gates: **dev** → `main`; **prod** → `release` ([workflow.md](workflow.md#git-before-deploy)).

Interactive shell: `.\scripts\dev-shell.ps1` — then `--local` or `deploy-fast.sh` inside container.

## Secrets

OpenAI, Pinecone, bot password: Key Vault → Function App settings (`infrastructure/keyvault.tf`, `functions.tf`). Terraform variables from repo `.env` — see [`infrastructure/README.md`](../../../infrastructure/README.md). Never commit keys.

## Troubleshooting (deploy / runtime)

| Symptom | Check |
|---------|--------|
| No reply | App Insights / health; Key Vault access |
| Streaming missing | 1:1 chat only; bot channel registered |
| Wrong Pinecone namespace | `sync-pinecone-appsettings` after deploy; tfvars |
| Broken citation links | Terraform `sharepoint_library_base_url` + KB human upload |

## Cost (rough)

Consumption Functions + Key Vault + Storage + OpenAI + Pinecone — order of magnitude tens–low hundreds USD/month for small tenant; verify with Azure/vendor pricing.

## Related

- [`scripts/README.md`](../../../scripts/README.md)
- [docker-images.md](docker-images.md)
- [`infrastructure/README.md`](../../../infrastructure/README.md)
