---

name: deployment-ops

description: >-

  Azure dev/prod deploy, Terraform infrastructure, Function App publish, and

  production changelog. Use when deploying bot code, running terraform plan/apply,

  syncing Pinecone app settings, or appending the deployments changelog. Not for

  corpus file changes (use knowledge-base-curator).

disable-model-invocation: false

---



# Deployment operations



Single entry point for **infrastructure + bot package deploy** — not corpus edits (→ `knowledge-base-curator`).



## Infrastructure (read before tfvars / first apply)



**[`infrastructure/README.md`](../../../infrastructure/README.md)** — resources created, multi-tenant dev/prod, tfvars checklist, outputs, destroy, troubleshooting. This skill covers *procedure*; that doc is the *spec*.



## One script per operation (repo root)



| Operation | Script | Windows CMD |

|-----------|--------|-------------|

| Terraform | `./scripts/terraform.sh <dev\|prod> <cmd> …` | `scripts\terraform.cmd dev plan` |

| Bot publish | `./scripts/deploy.sh <dev\|prod> [--terraform] [--full]` | `scripts\deploy.cmd prod --terraform` |



Both use the **`dev`** Docker image automatically. Inside `dev-shell`, same commands with `--local` or call `deploy-fast.sh` / `deploy-full.sh` directly.

| Also | Path |

|------|------|

| Changelog | [`docs/deployments/CHANGELOG.md`](../../../docs/deployments/CHANGELOG.md) |

| Runtime matrix | [docker-images.md](docker-images.md) |

| Commands / first-time | [workflow.md](workflow.md) |

| Architecture / smoke | [reference.md](reference.md) |



**Not your job:** Pinecone reindex, `source_data/` edits (KB curator coordinates *when* deploy is needed).

## Changelog

After every successful **prod** deploy on **`release`**, append [`docs/deployments/CHANGELOG.md`](../../../docs/deployments/CHANGELOG.md) in the same session. Commit on **`release`** with the deploy.

KB corpus mutations are logged separately in [`docs/knowledge-base/CHANGELOG.md`](../../../docs/knowledge-base/CHANGELOG.md) (knowledge-base-curator skill).



## Git, branches, and changelog (keep in sync)



Deploy scripts enforce branch ↔ environment. **Do not deploy from feature branches.**



| Deploy target | Required branch | Git meaning |

|---------------|-----------------|-------------|

| **dev** | `main` | Feature branch merged into `main` and **pushed** (`origin/main` reflects what you deploy) |

| **prod** | `release` | `main` merged into `release` and **pushed** before prod deploy |



**Prod changelog** ([`docs/deployments/CHANGELOG.md`](../../../docs/deployments/CHANGELOG.md)): append in the **same session** as a successful `./scripts/deploy.sh prod`. The **Git** line must be `git rev-parse HEAD` on `release` after the merge/push — not a feature-branch SHA.



Typical sequence:



```text

feature/* → PR/merge → main → push → deploy.sh dev → user smoke

main → merge → release → push → deploy.sh prod → deployments changelog entry → user smoke

```



## Approval gates



| Tier | Actions |

|------|---------|

| **0** | `terraform plan`, read outputs, `curl` health |

| **1** | `deploy.sh dev`, `terraform apply dev` | On **`main`** after merge |

| **2** | `deploy.sh prod`, `terraform apply prod`, changelog | On **`release`**; explicit user request |



**Prod checklist:**



1. `git checkout release && git merge main && git push origin release`

2. `./scripts/deploy.sh prod` (add `--terraform` / `--full` if needed)

3. Append [`docs/deployments/CHANGELOG.md`](../../../docs/deployments/CHANGELOG.md) (UTC, SHA on `release`, scope, verification)

4. User Teams smoke on prod



## Dev / prod commands



```powershell

# Dev (on main)

git checkout main; git pull origin main

.\scripts\deploy.cmd dev



# Infra + bot

.\scripts\deploy.cmd dev --terraform



# Prod (on release)

git fetch origin; git checkout release; git merge main; git push origin release

.\scripts\deploy.cmd prod --terraform

```



Terraform only: `.\scripts\terraform.cmd dev plan`



## Terraform vs deploy



| Step | Changes |

|------|---------|

| `terraform apply` | Azure resources, Key Vault, App Insights, app settings |

| `deploy.sh` (fast/full) | Python package; syncs Pinecone settings from tfvars |



`SHAREPOINT_LIBRARY_BASE_URL` — Terraform tfvars only ([`infrastructure/README.md`](../../../infrastructure/README.md)).



## When KB curator calls you



Dev validation on **`main`** → tier 1 deploy. Prod → tier 2 + changelog after **`release`** merge.



**First-time setup:** [workflow.md § First-time dev environment](workflow.md#first-time-dev-environment).



## Git commits



Do not commit unless user asks ([`git-commits.mdc`](../../rules/git-commits.mdc)).


