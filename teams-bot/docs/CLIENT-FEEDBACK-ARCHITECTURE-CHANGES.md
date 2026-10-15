# Northwind May 2026 feedback — architecture changes (code only)

**Branch:** `feature/client-feedback-investigation-2026-05`  
**Scope:** Bot/runtime changes only — **no** corpus/source edits (no pptx/pdf changes in repo).  
**RFC / checklist (design, not implementation):** corpus remediation [`../../pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md`](../../pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md); hybrid search design in [`../../docs/TASKS.md`](../../docs/TASKS.md) task **28**.

---

## What shipped in Wave 3 (this branch)

### 1. Clarification gate (`clarification_needed` / `respond_clarify`)

**Problem (B4, A9, A13):** Ambiguous queries (first lease vs extension, individual vs company) were answered with a guess instead of a short follow-up.

**Changes:**

| Area | Behavior |
|------|----------|
| **`RAGStrategy`** (`optimizer.py`) | New `clarification_needed: bool` and `clarification_questions: List[str]` (max 2). When true → `needs_rag=false`, no Pinecone call. |
| **Optimizer prompt** (`optimizer.py`) | Rules for when to ask (pierwsza umowa vs przedłużenie, osoba vs firma, vague procedural). Explicit opt-out for narrow questions (e.g. pozytywna kaucja). |
| **Routing** (`graph.py`) | `route_after_optimize` → `respond_clarify` when `clarification_needed`; new node `respond_clarify` → END. |
| **Node** (`nodes.py`) | `optimize` forces `needs_rag=false` when clarification set; `respond_clarify` returns formatted questions via `format_clarification_response`. |
| **Teams pipeline** (`teams_entry.py`, `graph.py` streaming) | Early exit: if optimizer sets clarification, stream/sync path calls `respond_clarify` without retrieve/answer LLM. |

### 2. Topic answer composer (`answer_composer.py`)

**Problem (B2, B3, A7, mixed deposit/termination answers):** Numeric answers buried; Procesy vs contract rules conflated.

**Changes:**

| Optimizer field | Values | Composer block |
|-----------------|--------|----------------|
| `answer_topic` | `none`, `deposit_kaucja`, `verification`, `early_termination` | Template for kaucja / weryfikacja / wcześniejsze rozwiązanie (Northwind examples in optimizer prompt). |
| `numeric_answer_first` | bool | When true, first sentence must state number/amount from CONTEXT. |

**Integration:** Optimizer sets fields on `RAGStrategy`; `nodes.py` / `teams_entry.py` pass them to `build_topic_composer_block(answer_topic, numeric_answer_first)` → `{topic_composer_block}` in `prompts.py`. No regex on the user question. When `clarification_needed=true`, `answer_topic=none`.

### 3. Tests added

| File | Covers |
|------|--------|
| `teams-bot/tests/test_answer_composer.py` | Enum-driven composer blocks, clarification formatting. |
| `teams-bot/tests/test_optimizer_clarification.py` | `optimize` sets `clarification_needed`, caps questions, skips RAG. |
| `teams-bot/tests/test_routing_clarification.py` | `route_after_optimize` → `respond_clarify`. |
| `teams-bot/tests/test_client_feedback_golden.py` | Golden file — expected `answer_topic` / `numeric_answer_first` → composer block (no live OpenAI/Pinecone). |

**Manual full repro:** `teams-bot/scripts/run_local_rag_tests.py --questions-file logs/client_feedback_golden.txt`

### 4. KQL misroute query

**File:** `scripts/kql/prod_client_feedback_misroute.kql`  
**Purpose:** Audit `retrieval_scope == "all"` on narrow tenant queries (wcześniejsze rozwiązanie, kaucja, weryfikacja, 12/24/36 mies.) — supports A5/A17 misroute analysis.  
**Companion:** `scripts/kql/prod_client_feedback_may2026.kql`, snapshot `logs/prod_client_feedback_may2026.json`.

### 5. RFC / checklist docs (not implementation)

| Doc | Role |
|-----|------|
| [acceptance-criteria.md](../../.cursor/skills/bot-quality-evaluation/acceptance-criteria.md) | Manual test cases A1–B5; issue taxonomy |
| [CLIENT-FEEDBACK-CORPUS-REMEDIATION.md](../../pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md) | P0 source owner actions + reindex steps (not bot code). |
| Task **28** in [TASKS.md](../../docs/TASKS.md) | Hybrid search design (deferred in Wave 3) |

---

## Files touched (code)

| File | Change summary |
|------|----------------|
| `teams-bot/rag/optimizer.py` | `clarification_*`, `answer_topic`, `numeric_answer_first`; prompt § doprecyzowanie + szablon odpowiedzi. |
| `teams-bot/rag/request_audit.py` | Task 36: `conversation_id`, `response_path`, clarify fields, `context_chunk_ids`, `sectionTitle` in compact sources. |
| `teams-bot/rag/graph.py` | `respond_clarify` node/edge; streaming + `build_teams_pipeline` clarification short-circuit. |
| `teams-bot/rag/nodes.py` | Clarification in `optimize`; `respond_clarify`; optimizer-driven composer in RAG answer path. |
| `teams-bot/rag/teams_entry.py` | Token stream clarification branch before retrieve. |
| `teams-bot/rag/prompts.py` | `{topic_composer_block}` placeholder in answer template. |
| `teams-bot/rag/answer_composer.py` | **New** — topic detection, composer blocks, clarification formatter. |
| `teams-bot/tests/test_answer_composer.py` | **New** |
| `teams-bot/tests/test_optimizer_clarification.py` | **New** |
| `teams-bot/tests/test_routing_clarification.py` | **New** |
| `teams-bot/tests/test_client_feedback_golden.py` | **New** |
| `scripts/kql/prod_client_feedback_misroute.kql` | **New** |

---

## Explicitly out of scope (this branch)

- Editing `pinecone-pipeline/source_data/` or **Procesy** pptx / contract PDFs.
- Pinecone hybrid index migration, BM25 sidecars, freshness metadata rerank (RFC only).
- In-chat user feedback widget (client “następne kroki”).

---

## Rollback (2026-05-28)

**Shipped tip:** `c639099` on `main` / `release` (dev validated, then prod).

**Reverted on investigation branch** (not merged — insufficient without broader architecture):

| Commit | Summary |
|--------|---------|
| `41ddcd0`–`c702b29` | 24m early-termination retrieval hacks |
| `2bd53df` | Retrieval v2 (`search_query`, multi-lane anchors) |
| `dbb9bb1` | Extended folder map; skip anchor lanes when prefix set |
| `1c2c698` | Structural clarify when corpus topic unknown |
| `80a0ab7` | Clarification follow-up → scoped RAG |

**Follow-up:** colloquial 24m / przedłużenie fee routing → task **28** (hybrid search in [TASKS.md](../../docs/TASKS.md)), [corpus remediation P0](../../pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md).

---

## Related evidence

Corpus excerpts and prod `trace_id` mapping: [CLIENT-FEEDBACK-CORPUS-REMEDIATION.md](../../pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md) and [acceptance-criteria.md](../../.cursor/skills/bot-quality-evaluation/acceptance-criteria.md).
