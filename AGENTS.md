# RAGStone — agent router

Load the **skill** for the domain before acting. Process and commands live in the skill, not scattered docs.

## Skills (source of truth)

| Skill | When to use |
|-------|-------------|
| [**knowledge-base-curator**](.cursor/skills/knowledge-base-curator/SKILL.md) | Corpus, Pinecone (`kb.sh`), changelog. **SharePoint:** human upload to `AI/dev` or `AI/prod`. |
| [**deployment-ops**](.cursor/skills/deployment-ops/SKILL.md) | Terraform, deploy — [`reference.md`](.cursor/skills/deployment-ops/reference.md), [`docs/deployments/CHANGELOG.md`](docs/deployments/CHANGELOG.md) |
| [**bot-quality-evaluation**](.cursor/skills/bot-quality-evaluation/SKILL.md) | Acceptance criteria, golden questions, KQL, `bot.sh` / `kql.sh` |

Always-on gateway rules enforce this: `.cursor/rules/*-gateway.mdc`.

## Docker (which container)

| Container | Role |
|-----------|------|
| `dev` | `kql.sh`, deploy, Terraform |
| `bot-test` | `bot.sh` — pytest, local RAG, probe |
| `pinecone-indexer` | `kb.sh` — index, reindex, delete |

[`docker-images.md`](.cursor/skills/deployment-ops/docker-images.md)

## Task tracking

- [`docs/TASKS.md`](docs/TASKS.md) — milestones; do not mark ✅ until user confirms testing ([`task-workflow.mdc`](.cursor/rules/task-workflow.mdc)).
- Git: commit/push only when user asks ([`git-commits.mdc`](.cursor/rules/git-commits.mdc)).

## Bot policy (code changes)

No keyword routing or embedded fee policy in prompts — [`teams-bot-no-hardcoded-routing.mdc`](.cursor/rules/teams-bot-no-hardcoded-routing.mdc).

