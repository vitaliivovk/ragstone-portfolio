# Knowledge base changelog

Living record of corpus, Pinecone, SharePoint, and routing changes. **Updated only by the knowledge-base-curator agent** after human-approved steps.

Git is the audit trail: commit this file with each approved change on the same branch as code/data ops.

---

## How to use

| Field | Meaning |
|-------|---------|
| **Change ID** | `KB-YYYY-MM-DD-NNN` (increment `NNN` per day) |
| **Status** | `planned` → `approved-dev` → `dev-applied` → `dev-validated` → `approved-prod` → `prod-applied` → `closed` |
| **Branch** | Feature branch for dev; **`release`** for prod Pinecone + bot deploy |

---

## Active operations

| Change ID | Status | Summary | Branch | Dev OK | Prod OK |
|-----------|--------|---------|--------|--------|---------|
| — | — | *No active operations* | — | — | — |

---

## Change log (newest first)

### KB-2026-05-31-001 — Remove duplicate Zakwaterowanie vectors in `v3`

| | |
|--|--|
| **Operation** | integrity cleanup (delete stale docIds) |
| **Approved by** | user @ 2026-05-31 |
| **Branch** | `release` (Pinecone-only; not committed yet) |

**Cause:** First index pass to `v3` only, then second pass (Docker `/data/docs/…`) without delete — different `docId` per path (path/mtime hash).

**Pinecone**
- Deleted **201 orphan vectors** from **`v3` only** (4 stale `docId`s):
  - `e1b240440c0bf9881c61ae4b05dbcbcad4176456`
  - `018664ac94b2969aaf4470b64001427e6ef41f6c`
  - `7b6461a38fc4539963446ac2298f05e31ae2cfcd`
  - `f3aa86a4764ab469506d7cb7ba975baffb061e9b`
- **`production` unchanged** (already canonical 201 vectors / 4 docIds).

**Integrity after cleanup**

| Namespace | `zakwaterowanie` vectors | docIds |
|-----------|------------------------|--------|
| `v3` | 201 | 4 (matches prod) |
| `production` | 201 | 4 |

**Tool:** `scripts/list_topic_doc_ids.py`, `delete_corpus_document.py --namespace v3`

---

<!-- Template — copy for each change:

### KB-YYYY-MM-DD-001 — Short title

| | |
|--|--|
| **Operation** | add \| edit \| delete \| promote-prod |
| **Approved by** | user @ ISO datetime |
| **Branch / commits** | `feature/…` → `abc1234`; prod `release` → `def5678` |

**Corpus**
- …

**Pinecone**
- Namespaces: `v3` / `production`
- Action: reindex \| delete `--source-relative-path …`
- Vector writes (if known): …

**SharePoint**
- Dev: sync \| **human upload** — path …
- Prod: …

**Bot routing**
- Files: …
- Deploy: dev `func-…-dev-…` \| prod `func-…-prod-…`

**Verification**
- Dev smoke: pending \| pass @ date
- Prod smoke: …

**Blockers / notes**
- …

-->

*Earlier corpus add / prod promote logged in git `711d7e5`, `07e2c9f`; Pinecone duplicate cleanup above.*

---

## Environment pointers

| Item | Dev | Prod |
|------|-----|------|
| Pinecone namespace | `v3` | `production` |
| SharePoint library suffix | `AI/dev` | `AI/prod` |
| Function App | see `infrastructure/environments/dev.tfvars` | see `prod.tfvars` |
| Bot deploy branch | feature branch OK | **`release` only** |

Reference: [knowledge-base-curator SKILL.md](../../.cursor/skills/knowledge-base-curator/SKILL.md), [workflow.md](../../.cursor/skills/knowledge-base-curator/workflow.md). Prod deploys: [deployments/CHANGELOG.md](../deployments/CHANGELOG.md).
