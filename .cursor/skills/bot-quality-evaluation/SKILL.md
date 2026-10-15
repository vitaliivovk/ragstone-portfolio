---
name: bot-quality-evaluation
description: >-
  Evaluate Teams bot answers against expected criteria: golden questions, topic
  checklists, App Insights RAG_TURN_AUDIT forensics, local RAG harness, and
  retrieval probes. Use when testing regressions, investigating a bad answer,
  comparing dev vs prod behavior, or validating a deploy. Not for corpus edits
  (knowledge-base-curator) or Azure deploy (deployment-ops).
disable-model-invocation: false
---

# Bot quality evaluation

Evaluate **answers and RAG decisions** — not mutate corpus or deploy unless the user asks another skill.

## Evidence in this skill folder

| Doc | Use for |
|-----|---------|
| [acceptance-criteria.md](acceptance-criteria.md) | **Northwind May 2026** — questions + MUST/SHOULD per issue (A1–B5, C4) |
| [corpus-qa-evaluation.md](corpus-qa-evaluation.md) | Grounded six-question run, Pinecone rank notes, chunk-boundary failure modes |
| [workflow.md](workflow.md) | KQL, regression sweep, classification |

**Question files (runtime):**

| File | Role |
|------|------|
| [`teams-bot/logs/client_feedback_golden.txt`](../../../teams-bot/logs/client_feedback_golden.txt) | One-liner per issue A1–A19 |
| [`teams-bot/logs/corpus_qa_questions.txt`](../../../teams-bot/logs/corpus_qa_questions.txt) | Six grounded corpus Q&A lines |

**Supporting docs (repo):** [`teams-bot/docs/CLIENT-FEEDBACK-ARCHITECTURE-CHANGES.md`](../../../teams-bot/docs/CLIENT-FEEDBACK-ARCHITECTURE-CHANGES.md), [`pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md`](../../../pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md).

## One script per operation (repo root)

| Operation | Script | Windows CMD |
|-----------|--------|-------------|
| Unit tests | `./scripts/bot.sh pytest tests/test_client_feedback_golden.py -q` | `scripts\bot.cmd pytest tests/ -q` |
| Full local RAG | `./scripts/bot.sh rag --file logs/client_feedback_golden.txt` | `scripts\bot.cmd rag --file logs/...` |
| Pinecone probe | `./scripts/bot.sh probe "pytanie" --top-k 8` | `scripts\bot.cmd probe "pytanie" --top-k 8` |
| App Insights KQL | `./scripts/kql.sh scripts/kql/last_rag_turn.kql` | `scripts\kql.cmd scripts\kql\...` |
| Optional host | `./scripts/bot.sh run func start` | — |

**Runtime:** `bot-test` image for bot.sh; `dev` image for kql.sh ([docker-images.md](../../deployment-ops/docker-images.md)).

## Evaluation lanes (pick one primary lane per investigation)

| Lane | When | Pass criteria |
|------|------|----------------|
| **A — Composer unit** | Prompt/routing structure only | `bot.sh pytest` green |
| **B — Local full RAG** | End-to-end answer text vs dev index | `bot.sh rag`; compare to [acceptance-criteria.md](acceptance-criteria.md) |
| **C — Retrieval only** | Wrong sources, not wording | `bot.sh probe`; top paths match expected doc family |
| **D — Live Teams** | UX, streaming, clarify gate | User fresh thread; score vs acceptance criteria |
| **E — Prod/dev logs** | Historical bad turn | `kql.sh` → `RAG_TURN_AUDIT` JSON → classify |

Do not run all lanes unless the user wants a full regression pass.

## Forensics template (Lane E)

After KQL returns a `RAG_TURN_AUDIT` row:

```markdown
## Turn evaluation

**trace_id / time:** …
**User question:** …
**response_path:** rag | clarify | handbook | smalltalk
**needs_rag:** … | **retrieval_scope:** … | **top paths:** …

### Expected (from acceptance-criteria / issue ID)
- …

### Actual answer (excerpt)
- …

### Classification
- [ ] DATA (corpus gap/wrong doc)
- [ ] RETRIEVAL (wrong scope/rank)
- [ ] GENERATION (CONTEXT had facts; answer wrong)
- [ ] CLARIFY (should have asked)

### Recommended owner skill
- knowledge-base-curator | bot code change | none
```

## Topic → test mapping

Use [`teams-bot/rag/folder_map_prompt.md`](../../../teams-bot/rag/folder_map_prompt.md) and corpus slugs. Full bullets: [acceptance-criteria.md](acceptance-criteria.md).

| Topic / slug | Golden IDs | Checklist |
|--------------|------------|-----------|
| Najem instytucjonalny / notarial | A1 | A1 |
| Weryfikacja / kaucja | A2, A3, A7, A15, B2 | A2, A3, … |
| Wcześniejsze rozwiązanie / 24m | A4–A6, A17 | extension docs |
| Zamiana | A10, A11 | multi-turn in Teams |

Add rows to **acceptance-criteria.md** when a new top-level corpus topic ships (ask KB curator).

## Grounded corpus Q&A tables

`./scripts/kb.sh qa-export --seed 42` → edit `pinecone-pipeline/agent_exports/corpus_qa_for_cursor.md` from quoted chunks only. See [workflow.md § Corpus Q&A export](workflow.md#corpus-qa-export) and [corpus-qa-evaluation.md](corpus-qa-evaluation.md).

## Git context (eval only)

| Check against | Branch / env |
|---------------|----------------|
| Dev Teams / local RAG | Code on **`main`** deployed to dev; Pinecone namespace **`v3`** |
| Prod investigation | Code on **`release`**; namespace **`production`** |

Eval does not deploy; hand off to **`deployment-ops`** when a fix must ship.

## Handoff

| Finding | Skill |
|---------|--------|
| Wrong/missing indexed content | `knowledge-base-curator` (`kb.sh`) |
| Deploy fix | `deployment-ops` (`deploy.sh` on `main` / `release`) |
| Bot logic only | Feature branch + re-run Lane B/C |

## Approvals

| Tier | Actions |
|------|---------|
| **0** | Read skill docs, KQL, pytest, probes, local RAG |
| **1** | None required for eval-only |

