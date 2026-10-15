# Northwind Assistant Bot - Azure Infrastructure

Terraform configuration to provision all Azure resources for the Teams bot.

**Extended docs:** [`docs/README.md`](docs/README.md) (GDPR / EU migration plan).

## Multi-Tenant Deployment

This infrastructure supports deploying to multiple Azure tenants:

- **dev** - Your development tenant (any branch)
- **prod** - Customer tenant, e.g., Northwind Residences (only from `release` branch)

### Branch protection (git ↔ deploy sync)

`scripts/terraform.sh`, `scripts/deploy.sh`, and `scripts/deploy/deploy-fast.sh` / `scripts/deploy/deploy-full.sh` enforce:

| Environment | Git branch | Meaning |
|-------------|------------|---------|
| **dev** | `main` | Feature work merged to `main` and pushed before dev deploy |
| **prod** | `release` | `main` merged into `release` and pushed before prod deploy |

Prod deploy changelog: [`docs/deployments/CHANGELOG.md`](../docs/deployments/CHANGELOG.md) — same session as deploy; Git SHA on `release`.

## Resources Created

| Resource | Type | Purpose |
|----------|------|---------|
| Resource Group | `azurerm_resource_group` | Container for all resources |
| App Registration | `azuread_application` | Bot identity (single-tenant) |
| Client Secret | `azuread_application_password` | Bot authentication |
| Azure Bot | `azurerm_bot_service_azure_bot` | Teams channel integration |
| Azure Functions | `azurerm_linux_function_app` | Bot backend (Python 3.11) |
| App Service Plan | `azurerm_service_plan` | Functions compute |
| Storage Account | `azurerm_storage_account` | Functions state |
| Key Vault | `azurerm_key_vault` | Secure secret storage |
| Log Analytics workspace | `azurerm_log_analytics_workspace` | Telemetry storage for the Function App |
| Application Insights | `azurerm_application_insights` | Linked to the workspace; `APPLICATIONINSIGHTS_CONNECTION_STRING` on the Function App |
| Container Apps env + LibreChat *(opt-in)* | `azurerm_container_app_environment` / `azurerm_container_app` | Web shell — **off by default** (`librechat_enabled = false`). See [`docs/LIBRECHAT-HOSTING.md`](docs/LIBRECHAT-HOSTING.md) |

The bot emits **one trace per Teams message** with prefix `RAG_TURN_AUDIT` and a JSON payload (user, message, answer, Pinecone index/namespace, metadata filter, retrieved paths, fallback flag). In Azure Portal: open **`appi-<project>-<env>`** (e.g. `appi-northwind-dev`) → **Monitoring → Logs** (not **Activity log**). Example: `traces | where message startswith "RAG_TURN_AUDIT" | order by timestamp desc`. **Verified working** on dev after `terraform apply` + bot deploy.

## Prerequisites

1. **Azure CLI** installed and logged in to the target tenant:
   ```bash
   az login --tenant <tenant-id>
   ```

2. **Terraform** >= 1.0.0 installed

3. **Azure permissions** in target tenant:
   - Contributor on subscription (for resource creation)
   - Application Administrator in Azure AD (for app registration)

## Initial Setup

### 1. Configure .env File

All sensitive configuration is loaded from `.env`. Add these variables:

```bash
# Azure tenant/subscription (terraform.sh picks by env: dev uses DEV_* or legacy AZURE_*; prod uses PROD_*)
DEV_AZURE_TENANT_ID=your-dev-tenant-id
DEV_AZURE_SUBSCRIPTION_ID=your-dev-subscription-id
PROD_AZURE_TENANT_ID=your-prod-tenant-id
PROD_AZURE_SUBSCRIPTION_ID=your-prod-subscription-id

# API keys
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
```

### 2. Environment Files (tfvars)

The tfvars files (`environments/dev.tfvars`, `environments/prod.tfvars`) set **region**, **Pinecone** (`pinecone_index_name`, `pinecone_namespace`), and **OpenAI** names on the Function App: `OPENAI_MODEL`, `OPENAI_OPTIMIZER_MODEL`, `OPENAI_EMBEDDING_MODEL` (must stay aligned with the Pinecone index / pipeline), plus `PINECONE_INDEX`, `PINECONE_INDEX_NAME`, `PINECONE_NAMESPACE`. They also set **`sharepoint_library_base_url`** (wired as **`SHAREPOINT_LIBRARY_BASE_URL`** on the Function App) for Teams **Źródła** deep links — see [`../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md`](../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md). Tenant/subscription IDs in tfvars target the right Azure directory; API keys come from `.env` as `TF_VAR_*` via `terraform.sh`.

**Production checklist (`prod.tfvars`):**

| Setting | Expected role |
|--------|----------------|
| `tenant_id` / `subscription_id` | Northwind Residences prod directory (not dev tenant) |
| `location` | e.g. `polandcentral` for prod RG |
| `pinecone_namespace` | `production` — same as `PINECONE_NAMESPACE_PROD` when indexing |
| `pinecone_index_name` | Same index the pipeline upserts to (e.g. `text-embedding-3-small`) |
| `openai_embedding_model` | Same as ingest embeddings (`text-embedding-3-small` ↔ 1536 dims) |
| `sharepoint_library_base_url` | SharePoint library folder URL for citation links (`AI/dev` vs `AI/prod`); empty string omits the app setting |

### 3. Create Release Branch (One-Time)

```bash
git checkout -b release
git push -u origin release
git checkout main
```

## Deployment Commands

Use the terraform wrapper script which handles environment selection, API key loading, and branch protection:

```bash
# Development deployment (any branch)
./scripts/terraform.sh dev init
./scripts/terraform.sh dev plan
./scripts/terraform.sh dev apply

# Production deployment (only from 'release' branch)
git checkout release
git merge main
./scripts/terraform.sh prod init
./scripts/terraform.sh prod plan
./scripts/terraform.sh prod apply
```

## Deploying Bot Code

After infrastructure is created, deploy the bot code:

```bash
# Development
./scripts/deploy/deploy-fast.sh dev

# Production (only from 'release' branch)
git checkout release
./scripts/deploy/deploy-fast.sh prod
```

## Building Teams App Package

After deployment, build the Teams app package with the bot ID:

```powershell
# Get bot ID from terraform
cd infrastructure
terraform output bot_app_id

# Build package
cd ../teams-app
.\build-package.ps1 -BotId "<bot-app-id>" -Environment dev  # or prod
```

## Outputs

After `terraform apply`, you'll get:

- `function_app_url` - URL for the Azure Functions app
- `bot_endpoint` - Messaging endpoint for Azure Bot
- `bot_app_id` - Application ID for Teams manifest
- `deploy_command` - Command to deploy the bot code

## Switching Between Tenants

When switching between dev and prod, you need to log in to the correct Azure tenant:

```bash
# For dev work
az login --tenant <your-dev-tenant-id>
./scripts/terraform.sh dev apply
./scripts/deploy/deploy-fast.sh dev

# For prod work (must be on release branch)
git checkout release
az login --tenant <customer-tenant-id>
./scripts/terraform.sh prod apply
./scripts/deploy/deploy-fast.sh prod
```

## LibreChat / Container Apps (Phase 2 scaffolding)

Additive stubs in [`librechat.tf`](librechat.tf). Default **`librechat_enabled = false`** so existing Teams/Functions `plan`/`apply` are unchanged.

When ready (Entra OIDC app, Mongo choice, soft-fork image): set variables per [`docs/LIBRECHAT-HOSTING.md`](docs/LIBRECHAT-HOSTING.md), then `./scripts/terraform.sh <env> plan`. Secrets only via `TF_VAR_*` / Key Vault — never commit. Do not enable on prod until a successful dev pilot.

Config for the soft fork lives in [`librechat/`](../librechat/); RAG adapter is FastAPI under `teams-bot/web/` (not Functions SSE).

## Environments

- **dev**: Uses F0 (free) bot tier, Y1 (consumption) functions
- **prod**: Uses S1 (standard) bot tier, P1v2 functions with always-on

## Destroying Resources

```bash
# Destroy dev environment
./scripts/terraform.sh dev destroy

# Destroy prod environment (only from release branch)
git checkout release
./scripts/terraform.sh prod destroy
```

⚠️ This will delete ALL resources including the Key Vault with secrets.

## Troubleshooting

### "Authorization failed"
Ensure you're logged in to the correct tenant:
```bash
az login --tenant <tenant-id>
az account show
```

### "Production deployments only allowed from 'release' branch"
You must be on the `release` branch to deploy to prod:
```bash
git checkout release
git merge main
```

### "App registration failed"
You need Application Administrator role in Azure AD for the target tenant.

### "Key Vault access denied"
Wait a few seconds for RBAC propagation, then retry.
