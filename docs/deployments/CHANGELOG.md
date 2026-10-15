# Deployments changelog

Living log of **production** Azure Functions deploys. **Dev** deploys are not listed unless noted for correlation.

**Updated only** as part of a successful prod deploy (same session). Git is the audit trail: commit this file on **`release`** with the deploy.

**Policy:** [deployment-ops SKILL.md](../../.cursor/skills/deployment-ops/SKILL.md) · **How-to:** [workflow.md § changelog](../../.cursor/skills/deployment-ops/workflow.md#changelog)

## How to log an entry

Append a new section **after** a successful prod deploy (`./scripts/deploy.sh prod`, branch **`release`**).

Each entry: UTC time, git SHA on `release`, scope (bot vs infra), notable changes, verification (health + Teams smoke).

KB corpus changes logged separately in [`knowledge-base/CHANGELOG.md`](../knowledge-base/CHANGELOG.md).

---

## 2026-04-10 — Teams bot (inner RAG, status milestones, citations, folder map)

- **When (UTC):** ~2026-04-10 04:05 (deploy completed successfully).
- **Git:** application merge `2449fe0` on `release` (fast-forward `fix/teams-streaming-cumulative` → `main` → `release`); `release` tip `5f1904e` adds deploy-log SHA line only.
- **Azure:** Function App `func-northwind-prod-xxxxx`, RG `rg-northwind-prod`. Health: `https://func-northwind-prod-xxxxx.azurewebsites.net/api/health`.
- **Scope:** Bot package only (`teams-bot` → Azure Functions prod workspace). Pinecone app settings synced from `infrastructure/environments/prod.tfvars` by `scripts/lib/sync-pinecone-appsettings.sh` (`PINECONE_NAMESPACE=production`, index `text-embedding-3-small`).
- **Notable changes:**
  - Deep Agent + inner `run_teams_turn_nonstream`; real user message for inner RAG.
  - Polish informative status lines (optimize / retrieve / phases); post-retrieve copy documents **LLM answer generation** phase.
  - `CITATIONS_USED` filtering and related prompt/citation pipeline.
  - Optimizer/history and folder-path/corpus hints (task 24 groundwork).
  - Removal of outer-token “thinking” informative mirror in `function_app.py`.
  - Inner pipeline timing logs in Application Insights traces (`teams_pipeline_*_ms`).
- **Verification:** `https://<prod-function-app>.azurewebsites.net/api/health` → `healthy`; send a 1:1 Teams message in **production** tenant and confirm status text + answer + sources.

---

## 2026-04-17 — Teams bot (latency, anchor retrieval, citations UX)

- **When (UTC):** ~2026-04-17 (after merge to `release` and prod deploy).
- **Git:** `96fefe1` on `release` (includes `feature/latency-fix-notes-cleanup`).
- **Azure:** Function App `func-northwind-prod-xxxxx`, RG `rg-northwind-prod`. Health: `https://func-northwind-prod-xxxxx.azurewebsites.net/api/health`.
- **Scope:** Bot package + Pinecone app settings sync from `infrastructure/environments/prod.tfvars`.
- **Notable changes:**
  - Lean Teams path (no outer Deep Agent); `reasoning_effort=minimal` on optimizer + answer LLMs; slimmer `RAGStrategy` and shorter optimizer / folder-map prompts.
  - Parallel anchor semantic retrieval for two fixed Instrukcje handbook paths (`RAG_ANCHOR_*` settings).
  - Citations: `should_attach_source_block` fix for partial „nie znalazłem…” disclaimers; inline bracket alignment with `CITATIONS_USED`; same-document comma collapse for stacked `[Źródło N]` (`RAG_INLINE_SAME_DOC_CITATION_COLLAPSE_ENABLED`).
  - Status copy no longer exposes internal `chunks_only` tier label; Table Storage history cache + limits.
- **Verification:** prod `/api/health` → `healthy`; 1:1 Teams smoke including **Źródła** when the model cites sources.

---

## 2026-05-08 — Teams bot (SharePoint citation links, `/style`, prompts)

- **When (UTC):** ~2026-05-07 23:07 (Azure Function App deployment — active through 2026-05-27); git commit `1ce0469` at 2026-05-08 01:04 +0200.
- **Git:** `1ce0469` on `release` (`50bd270`, `919c3d2` prep commits on 2026-05-07).
- **Azure:** Function App `func-northwind-prod-xxxxx`, RG `rg-northwind-prod`. Health: `https://func-northwind-prod-xxxxx.azurewebsites.net/api/health`.
- **Scope:** Bot package + Pinecone app settings sync; Terraform **`sharepoint_library_base_url`** applied so prod Function App has **`SHAREPOINT_LIBRARY_BASE_URL`** = `…/Shared%20Documents/AI/prod`.
- **Notable changes (since 2026-04-24):**
  - **SharePoint deep links** in **Źródła** — one list row per file, merged page labels; PDF vs Office URL rules.
  - **`/style` / `/styl`** — per-user answer preferences in Azure Table `userpreferences`; injected into answer + optimizer prompts.
  - Answer-style overhaul — paraphrase (not verbatim chunks), neutral tone, **Najważniejsze punkty** bullet block for long answers.
  - Citation/streaming hardening in `citations.py` and `bot/streaming.py`; markdown **Źródła** with clickable links.
- **Verification:** prod `/api/health` → `healthy`; Teams smoke — cited answer shows **Źródła** links under `AI/prod`, `/style krótko` persists preference.

---

## 2026-05-28 — Teams bot (Northwind Wave 3: clarify gate, composer, folder map)

- **When (UTC):** ~2026-05-28 21:35 dev smoke (`func-northwind-dev-xxxxx`); ~2026-05-28 21:54 prod (`func-northwind-prod-xxxxx`).
- **Git:** `9f69a02` on `release` (bot tip `c639099` + deploy docs; merge `feature/client-feedback-investigation-2026-05` → `main` → `release`).
- **Azure:** Function App `func-northwind-prod-xxxxx`, RG `rg-northwind-prod`. Health: `https://func-northwind-prod-xxxxx.azurewebsites.net/api/health`.
- **Scope:** Bot package + Pinecone app settings sync (`PINECONE_NAMESPACE=production`).
- **Notable changes (since 2026-05-08 / `1ce0469`):**
  - **Clarification gate** — `clarification_needed` + max 2 questions; `respond_clarify` path (no Pinecone); LLM-only (no regex fallback).
  - **Answer composer** — `answer_topic` + `numeric_answer_first` via `teams-bot/rag/answer_composer.py`.
  - **Procesy deck removed** from handbook, anchors, prompts (`d134463`).
  - **Retrieval** — anchor + primary merged by Pinecone score; `MAX_RAG_CONTEXT_CHARS=48000`; conflict-handling answer rules.
  - **Handbook direct off** — `RAG_HANDBOOK_DIRECT_ENABLED=0`; Instrukcja via anchor + full RAG.
  - **Contract folder map** — extended `folder_map_prompt.md`; CONTEXT-only composer blocks (no embedded fee amounts).
  - **Audit (partial task 36):** `conversation_id`, `response_path`, clarify fields, `context_chunk_ids` in `RAG_TURN_AUDIT`.
- **Not shipped:** 24m colloquial routing experiments, retrieval v2, full-document prefix load, clarification follow-up resolver — deferred (RFC / hybrid search).
- **Verification:** dev + prod `/api/health` → `healthy`; Teams smoke — clarify on ambiguous lease stage; kaucja with lead numeric sentence; no Procesy deck in retrieval.

---

## 2026-05-29 — Teams bot (Instrukcja Northwind deposit example)

- **When (UTC):** ~2026-05-29 11:50 prod (`func-northwind-prod-xxxxx`); dev smoke earlier same day.
- **Git:** `5684455` on `release` (merge `feature/instrukcja-kaucja-northwind-2026-05`).
- **Azure:** Function App `func-northwind-prod-xxxxx`, RG `rg-northwind-prod`. Health: `https://func-northwind-prod-xxxxx.azurewebsites.net/api/health`.
- **Scope:** Bot package (`handbook_corpus.json`) + Pinecone app settings sync. Corpus/Pinecone vectors for Instrukcja DOCX+PDF reindexed earlier to **`production`** namespace (operator run).
- **Notable changes:**
  - **Instrukcja 2025** — explicit Northwind deposit example (a flat holding deposit, refusal on identity/sanctions) in handbook + indexed chunks.
  - **Selective reindex** — `pinecone-pipeline/scripts/reindex_files.py`, `patch_instrukcja_kaucja.py`; task **37** logged.
- **Verification:** dev Teams — positive verification → standard holding deposit; negative credit check → higher holding deposit; prod `/api/health` → `healthy`.
