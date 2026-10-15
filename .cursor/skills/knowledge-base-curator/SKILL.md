---
name: knowledge-base-curator
description: >-
  Mandatory entry point for ALL knowledge base operations (read and write): corpus
  files, Pinecone, folder-map/routing prompts, SharePoint mirrors, KB state/history.
  Use when the user asks about documents in source_data, indexing, retrieval scopes,
  citation paths, reindex/delete, or corpus change log. Mutations need human approval;
  read-only work proceeds without approval. Other agents must load this skill before any KB touch.
disable-model-invocation: false
---

# Knowledge base curator

You are the **single entry point** for all knowledge-base work — **read and write**. Process and tooling live here so the project changes approach in one place ([workflow.md](workflow.md)).

Other agents must **load this skill** before any KB touch (including listing files or running probes). They must not duplicate KB logic elsewhere.

## Surfaces you own

| Surface | Path / tool | Read (no approval) | Mutate (approval required) |
|---------|-------------|--------------------|----------------------------|
| Corpus files | `pinecone-pipeline/source_data/` | Yes | Add / replace / remove |
| Pinecone | `pinecone-indexer` Docker | Probes, namespace checks | `reindex_files.py`, `delete_corpus_document.py`, `ragstone-index` |
| Topic metadata | `pinecone-pipeline/corpus_metadata.py` | Yes | New top-level folder |
| Bot routing | `folder_map_prompt.md`, `retrieval_filter.py`, `status_copy.py` | Yes | Routing edits |
| Folder map doc | `opis folderów.docx`, `source_data/README.md` | Yes | Updates |
| SharePoint mirror | **Human upload** to `AI/dev/` or `AI/prod/` | Explain paths & status | Instruct user; do not rely on agent sync |
| Changelog | `docs/knowledge-base/CHANGELOG.md` | Yes | After approved mutations |
| Bot deploy | — | — | Delegate to **`deployment-ops`** skill after KB validation |

**Not your job:** Teams bot logic outside routing prompts, Terraform (except SharePoint base URL notes), general app code.

**Narrow exception:** filling `pinecone-pipeline/agent_exports/` Q&A tables — follow [corpus-qa-agent-pack.mdc](../../rules/corpus-qa-agent-pack.mdc) when that glob is the sole task; still load this skill if the request mixes KB read + Q&A eval.

## Read-only operations (no approval — proceed immediately)

Load this skill and execute without a plan/approve gate:

- List or read files under `source_data/`, `chunk_output/` JSONL, `corpus_metadata.py`, folder map prompts
- Explain slugs, `corpusTopic`, namespaces (`v3` vs `production`), SharePoint vs Pinecone
- Run **`probe_pinecone_retrieval.py`**, read-only Pinecone validation, KQL on `corpusTopic` / `retrieved_documents`
- Read [`CHANGELOG.md`](../../../docs/knowledge-base/CHANGELOG.md) and summarize change history
- Compare namespace health (vector totals, same-path doc counts in `v3` vs `production`) and **report duplication/skew risks to the human**
- Draft a **hypothetical** add/edit/delete plan when user asks “what would we do?” — label it *draft only, not executed*

Do **not** write state-log entries for pure read-only sessions unless the user asks to record an investigation note.

## Mandatory gates (mutations only)

### 1. Plan → wait for approval (every mutation)

Before **any** file copy, delete, reindex, delete vectors, routing edit, deploy, or SharePoint sync, post:

```markdown
## Proposed knowledge base change

**Operation:** add | edit | delete | promote-prod
**Change ID:** KB-YYYY-MM-DD-NNN (allocate next in CHANGELOG.md)

### What will change
- Corpus: `<path>` — added | replaced | removed
- Pinecone: `<namespaces>` — upsert | delete by path/docId
- Bot routing: yes/no — files list
- SharePoint: automated sync | **human upload** to `AI/dev/...` or `AI/prod/...`
- Branch: `feature/...` (dev) | `release` (prod data + deploy)

### Commands (will run after approval)
1. …
2. …

### Data integrity risks (required — see below)
- Duplication: …
- Stale vectors: …
- Namespace skew: …
- Mitigation in this plan: …

**Reply `approve` to proceed with dev only, or edit the plan.**
```

**Stop.** Do not run mutating commands until the user approves.

### 2. Dev first

After approval:

1. Work on a **feature branch** (never `main` / `release` for dev iteration).
2. Pinecone: `.env` with `PINECONE_NAMESPACE_DEV=v3`, `PINECONE_NAMESPACE_PROD=` **empty** unless user explicitly allows dual upsert on first index.
3. Index via **Docker only** (see [workflow.md](workflow.md)).
4. Deploy bot to **dev** if routing changed.
5. Ask user to **smoke-test dev Teams** or load **`bot-quality-evaluation`** for probes/KQL.
6. Log progress in `CHANGELOG.md` (status `dev-pending-validation` → `dev-validated`).

### 3. Prod only after dev sign-off

When user confirms dev is OK, post a **second approval** for prod:

- Merge to `release` (code + changelog).
- Reindex with `PINECONE_NAMESPACE_PROD=production` (and dev if keeping parity).
- SharePoint `AI/prod/...` — **human upload**.
- Load **`deployment-ops`** → prod deploy on **`release`** + [`docs/deployments/CHANGELOG.md`](../../../docs/deployments/CHANGELOG.md).
- Update changelog: `prod-promoted`, git SHAs.

Never prod reindex/deploy in the same turn as dev without explicit two-step approval.

## Data integrity — always inform the human

**You must surface duplication and corruption risks** — not only when asked. Do this in **every mutation plan**, **after every index/delete**, and in **read-only audits** when you detect or suspect issues.

Full risk catalog and checks: [workflow.md § Data integrity](workflow.md#data-integrity-risks-and-checks).

### Why duplicates happen (tell the human in plain language)

Pinecone vector ids come from **`docId` + chunk/summary index**. `docId` = SHA1(**absolute file path** + **file mtime**). Upsert **replaces** only the **same id**; it does **not** remove old docs.

| Risk | How it happens | Symptom | Mitigation |
|------|----------------|---------|------------|
| **Orphan vectors after reindex** | Reindex without `delete_corpus_document.py` first; path or mtime changed | Same `sourceRelativePath` appears twice in retrieval; namespace vector count higher than expected | Delete by old `--source-relative-path` or `--doc-id`, then reindex once |
| **Host vs Docker path** | Index on Windows host (`C:\…`) then in container (`/data/docs/…`) | **Double set in `v3`**; prod may look fine if only Docker run hit prod | **Always** index via `pinecone-indexer` Docker |
| **Double pass to same namespace** | Dev-only index to `v3`, then second index with both namespaces without cleaning `v3` | `v3` ≈ 2× vector count vs `production` for same folder | Before second pass: delete prior vectors in affected namespace(s) or accept cleanup step |
| **Namespace skew** | Upsert to `v3` only; prod bot unchanged | Prod missing docs; delta = whole folder’s vector count | Promote: upsert to `production`; verify both namespaces |
| **Edit/rename without delete** | File replaced or moved; new `docId` | Stale answers from old chunks still retrievable | Delete old path/docId → reindex |
| **SharePoint path drift** | File on disk ≠ `AI/dev` or `AI/prod` mirror | Citations 404; RAG still works | Sync/upload; not a Pinecone dup but report as **citation corruption** |
| **Cache vs Pinecone drift** | `--force` local cache but no Pinecone delete | JSONL new, Pinecone mixed old+new ids | Delete Pinecone rows for path, then `--force` reindex |
| **Partial failure** | Reindex stopped mid-batch | Some files indexed, others not | Report which paths finished; do not assume folder complete |

### When to warn (mandatory)

1. **Before approval:** fill **Data integrity risks** in the plan (even if “none identified” — state why).
2. **After upsert/delete:** short **Integrity report** to the human:
   - Namespaces touched
   - Per-file: expected vectors (chunks + summaries from log) vs upsert row count
   - Whether a **prior index** of the same paths is known (changelog / git / user said so)
   - Recommend **namespace compare** if same paths were indexed before on any namespace
3. **On read/probe:** if counts or paths look wrong, report immediately — do not silently proceed with new writes.

### Reindex safety defaults (include in plans)

- Index **only** inside `pinecone-indexer` (never host `uv` on Windows for corpus paths).
- **Second index** of the same paths → plan explicit **delete-by-`sourceRelativePath`** in target namespace(s) first, unless user accepts duplicate risk.
- **Edit/rename/move** → delete old Pinecone rows **before** reindex.
- **Promote dev → prod** → upsert `production`; optionally verify `v3` not doubled after prior dev-only run.
- Record `docId`(s) from `chunk_output/*.jsonl` filename suffix in the changelog when possible.

### Post-operation integrity report template

```markdown
## Knowledge base integrity report

**Change ID:** KB-…
**Namespaces:** v3 | production

| sourceRelativePath | Action | Vectors upserted/deleted | Prior index known? | Risk |
|--------------------|--------|--------------------------|--------------------|------|
| … | reindex | … | yes/no | dup / skew / none |

**Recommended follow-up:** none | delete stale in v3 | compare namespaces | user smoke
```

## Changelog (required)

After every approved step, update [`docs/knowledge-base/CHANGELOG.md`](../../../docs/knowledge-base/CHANGELOG.md):

- Allocate `KB-YYYY-MM-DD-NNN`
- Record plan, approvals, commands run, namespaces, commits, blockers
- Track SharePoint steps done by **human** vs agent
- Log **integrity report** (risks + recommended follow-up) after each Pinecone write

Commit changelog with related code on the same branch as the change.

## One script per operation (repo root)

| Operation | Script | Windows CMD |
|-----------|--------|-------------|
| Reindex file(s) | `./scripts/kb.sh reindex "Topic/file.docx" [--force]` | `scripts\kb.cmd reindex "Topic\file.docx"` |
| Delete vectors | `./scripts/kb.sh delete --source-relative-path "…"` | `scripts\kb.cmd delete --source-relative-path "…"` |
| Full corpus index | `./scripts/kb.sh index` | `scripts\kb.cmd index` |
| Chunk Q&A export | `./scripts/kb.sh qa-export --seed 42` | `scripts\kb.cmd qa-export --seed 42` |
| SharePoint sync (optional) | `./scripts/kb.sh sharepoint …` | `scripts\kb.cmd sharepoint …` |

All Pinecone commands use **`pinecone-indexer`** Docker automatically. **Human SharePoint upload** remains default (see below).

| Reference | Path |
|-----------|------|
| Corpus layout / ingest | [`pinecone-pipeline/README.md`](../../../pinecone-pipeline/README.md) |
| Citations / SharePoint URLs | [citation-sharepoint-links.md](citation-sharepoint-links.md) |
| Folder map | [folder-map-prompt.md](folder-map-prompt.md) |
| Changelog | [`docs/knowledge-base/CHANGELOG.md`](../../../docs/knowledge-base/CHANGELOG.md) |
| Workflows | [workflow.md](workflow.md) |
| Bot deploy after routing | **`deployment-ops`** — `scripts/deploy.sh` on **`main`** (dev) / **`release`** (prod) |
| Answer quality check | **`bot-quality-evaluation`** — `scripts/bot.sh` / `scripts/kql.sh` |

## SharePoint (citations) — human upload default

Automated sync (`scripts/kb.sh sharepoint` → `sharepoint_sync.py`) often fails with **access rights** (delegated device flow or `Sites.Selected` not granted). **Default:**

1. Tell the human the exact SharePoint folder: `Shared Documents/AI/dev/<sourceRelativePath>` or `AI/prod/...` (must match Terraform `sharepoint_library_base_url`).
2. Record in the mutation plan: **SharePoint: human upload** — not agent sync.
3. Only attempt `sharepoint_sync.py` if the user explicitly says credentials/grants are fixed; on 401/403 → stop and revert to human upload.

Citation URL rules: [citation-sharepoint-links.md](citation-sharepoint-links.md).

Do **not** use host `uv` for Pinecone on Windows (Unicode paths). Rebuild `pinecone-indexer` after pipeline **code** changes (COPY in Dockerfile).

## Workflows

Detailed add / edit / delete: [workflow.md](workflow.md)

Contributor-facing rules: [citation-sharepoint-links.md](citation-sharepoint-links.md).

## Git (keep code, index, and deploy in sync)

| Stage | Branch | Meaning |
|-------|--------|---------|
| KB iteration | `feature/…` | Corpus/routing edits and Pinecone **dev** (`v3`) |
| Dev bot deploy | `main` | Feature merged to `main` → `deployment-ops`: `./scripts/deploy.sh dev` |
| Prod promote | `release` | `main` merged to `release` → reindex `production` + `./scripts/deploy.sh prod` |

- Commit when user asks; include `CHANGELOG.md` with mutations.
- Do not commit secrets, `chunk_output/`, or bulk binaries unless policy changes.
