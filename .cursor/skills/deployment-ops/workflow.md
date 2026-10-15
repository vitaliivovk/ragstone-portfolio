# Deployment workflow reference

Infrastructure spec: **[`infrastructure/README.md`](../../../infrastructure/README.md)**.

## Git before deploy

| Target | Branch | Before running deploy |
|--------|--------|------------------------|
| dev | `main` | Merge feature → `main`, `git push origin main`, `git checkout main && git pull` |
| prod | `release` | `git merge main` on `release`, `git push origin release` |

Scripts: `scripts/lib/git-deploy-branch.sh` (used by `terraform.sh`, `deploy.sh`, `deploy-fast.sh`, `deploy-full.sh`).

## First-time dev environment

**Prerequisite:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) running.

**Start devops shell** (repo root):

```powershell
.\scripts\dev-shell.ps1
```

```bash
./scripts/dev-shell.sh
```

**Inside the container** (or use host `terraform.sh` / `deploy.sh` which wrap Docker):

```bash
az login   # persists in azure-config volume
az account set --subscription "<name-or-id>"   # or DEV_AZURE_SUBSCRIPTION_ID in .env
./scripts/terraform.sh --local dev init
./scripts/terraform.sh --local dev apply
./scripts/deploy.sh --local dev --full
```

Copy `infrastructure/terraform.tfvars.example` → `terraform.tfvars` and edit per [`infrastructure/README.md`](../../../infrastructure/README.md).

Repo **`.env`**: `OPENAI_API_KEY`, `PINECONE_API_KEY`, `DEV_AZURE_*` / `PROD_AZURE_*`.

**Host one-shot** (repo root):

```powershell
.\scripts\deploy.cmd dev --terraform   # first stack
.\scripts\deploy.cmd dev               # code only (on main)
```

Image details: [docker-images.md](../docker-images.md).

### Troubleshooting

| Issue | Fix |
|-------|-----|
| Docker not running | Start Docker Desktop |
| `az login` blocked | Firewall / login.microsoftonline.com |
| Terraform state from host | `terraform init -migrate-state` inside container |
| Wrong branch | See **Git before deploy** |

## Decision table

| Scenario | Command |
|----------|---------|
| First dev deploy | `./scripts/deploy.sh dev --full` (often `--terraform` first) |
| `requirements.txt` changed | `./scripts/deploy.sh dev --full` |
| Code-only (on `main`) | `./scripts/deploy.sh dev` |
| `deploy-fast` fails | `./scripts/deploy.sh dev --full` |
| Infra/tfvars changed | `./scripts/deploy.sh dev --terraform` |
| Prod release (on `release`) | `./scripts/deploy.sh prod` → changelog |

## Terraform

```bash
./scripts/terraform.sh dev plan
./scripts/terraform.sh dev apply -auto-approve
```

Windows: `scripts\terraform.cmd dev plan`

Prod: **`release`** branch only. Workspaces: dev = `default`, prod = `prod`.

Outputs: `cd infrastructure && terraform output` (see [`infrastructure/README.md`](../../../infrastructure/README.md)).

## Health verification

```bash
curl "https://<function_app_host>/api/health"
```

## Changelog {#changelog}

[`docs/deployments/CHANGELOG.md`](../../../docs/deployments/CHANGELOG.md) — **only after successful prod deploy on `release`**. Git SHA in the entry must match the deployed commit.

```markdown
## YYYY-MM-DD — short title

- **When (UTC):** …
- **Git:** `<sha>` on `release`
- **Scope:** bot only | terraform + bot
- **Notable changes:** …
- **Verification:** health URL + Teams smoke
```

## Environment / `.env`

`DEV_AZURE_*` / `PROD_AZURE_*` for `az account set`. Docker `azure-config` volume persists login.

