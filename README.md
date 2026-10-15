# RAGStone

> **Portfolio version.** This repository is a copy of a real client project, shared for portfolio purposes. Because the original engagement is confidential, company and product names, contact details, Azure tenant and subscription identifiers, and resource names were changed, and client documents (knowledge-base corpus, employee handbook, invoices, rendered customer packs, incident logs) were removed. "Northwind Residences" and "Northwind Assistant" are fictional stand-ins. Git history from the original repository is not included.



Microsoft Teams assistant backed by **Azure Functions**, **LangGraph** RAG, **Pinecone**, and **OpenAI**, with Terraform-managed Azure infrastructure.



## Documentation



**Cursor agents:** start from **[`AGENTS.md`](AGENTS.md)** — load the skill for your domain before acting.



| Skill | Role |

|-------|------|

| [`knowledge-base-curator`](.cursor/skills/knowledge-base-curator/SKILL.md) | Corpus, Pinecone, SharePoint citations — `scripts/kb.sh` |

| [`deployment-ops`](.cursor/skills/deployment-ops/SKILL.md) | Terraform, deploy, prod changelog |

| [`bot-quality-evaluation`](.cursor/skills/bot-quality-evaluation/SKILL.md) | Golden questions, KQL — `scripts/bot.sh`, `scripts/kql.sh` |



**Human / project docs** (not duplicated in skills):



| Path | Role |

|------|------|

| [`docs/TASKS.md`](docs/TASKS.md) | Roadmap and task status |

| [`docs/knowledge-base/CHANGELOG.md`](docs/knowledge-base/CHANGELOG.md) | KB changelog (updated on approved mutations) |
| [`docs/deployments/CHANGELOG.md`](docs/deployments/CHANGELOG.md) | Prod deploy changelog (append after each prod release) |

| [`docs/customer-support/`](docs/customer-support/) | Admin setup (EN/PL) and bot user guides |

| [`teams-bot/docs/`](teams-bot/docs/) | Bot UX notes and investigations |

| [`pinecone-pipeline/docs/`](pinecone-pipeline/docs/) | Corpus remediation, vector DB comparison |

| [`infrastructure/docs/`](infrastructure/docs/) | GDPR / EU migration plan |



Skill reference docs (process + operators): [KB citations](.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md), [Docker images](.cursor/skills/deployment-ops/docker-images.md).



## Quick start (developers)



```powershell

.\scripts\dev-shell.ps1

```



Inside the container: `az login`, then `./scripts/terraform.sh dev apply` (see **`deployment-ops`** [`workflow.md`](.cursor/skills/deployment-ops/workflow.md)).



## Repository layout



| Path | Role |

|------|------|

| `infrastructure/` | Terraform (Bot, Functions, Key Vault, …) |

| `teams-bot/` | Python Azure Functions bot |

| `teams-app/` | Teams manifest + `build-package.ps1` (zip artifacts are gitignored) |

| `pinecone-pipeline/` | Document chunking and Pinecone indexing (`uv`) |

| `scripts/` | `dev-shell`, Terraform wrapper, `deploy-fast` / `deploy-full` |

| `docs/` | Task tracker, changelogs, customer guides |


