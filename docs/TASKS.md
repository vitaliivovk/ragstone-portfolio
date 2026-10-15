# RAGStone Tasks

**Git sync (2026-06-29):** `release` at **`a161cb3`** (5 commits ahead of `main` at **`bcc5ce5`**). `documentation-refactor` adds doc-only commits on top of `release`.

## Active Tasks

### 39. LibreChat web shell + RAG OpenAI-compatible adapter

**Priority:** High

**Status:** 🔄 In Progress — Phase 0/1 done; Phase 2–5 scaffolding + **Phase 6 connectors/multi-tenant docs** + deferred Bedrock track note on branch `feature/librechat-web-shell` (no deploy / no Graph consent / no terraform apply)

**Goal:** Soft-fork LibreChat (config only) as the web chat shell; expose the existing `teams-bot/rag` pipeline as an OpenAI-compatible custom endpoint (`/v1/chat/completions` SSE). Keep OpenAI + Pinecone. Teams bot path unchanged.

**Plan:** Office IDE roadmap (`office_ide_roadmap_*.plan.md` — human-owned; do not edit from agents). Absorbs intent of task **15** (web surface); Entra app roles supersede task **25** allowlist for the web channel.

**Phases (this task):**
- **Phase 0** — Spike docs + LibreChat config scaffolding (`docs/office-ide/`, `librechat/`).
- **Phase 1** — RAG web adapter (`teams-bot/web/`), unit tests, local run entry. FastAPI sidecar (not Functions) for reliable SSE.
- **Phase 2** — Azure Container Apps + Mongo + Entra OIDC tenant lock (infra).
- **Phase 3** — MCP plugin framework (SharePoint + Teams stubs; OBO / Graph later — tasks **14c**, **35**).
- **Phase 4** — Process/workflow engine v1 (definitions + catalog + dry-run; first process = standard client reply → email draft, never send).
- **Phase 5** — Conversation mining (Mongo + `RAG_TURN_AUDIT` → candidate processes) + frontend exit decision gate ([`FRONTEND-EXIT-CRITERIA.md`](office-ide/FRONTEND-EXIT-CRITERIA.md)).
- **Phase 6** — Outlook + Salesforce MCP stubs; multi-tenant + real-estate vertical docs; admin dashboard later.
- **Deferred** — AWS Bedrock / EU-GDPR migration (swap inside RAG service only; see [`BEDROCK-DEFERRED.md`](office-ide/BEDROCK-DEFERRED.md), task **12**, `infrastructure/docs/GDPR-MIGRATION-PLAN.md`).

**Docs:** [`docs/office-ide/LIBRECHAT-SPIKE.md`](office-ide/LIBRECHAT-SPIKE.md), [`docs/office-ide/FRONTEND-EXIT-CRITERIA.md`](office-ide/FRONTEND-EXIT-CRITERIA.md), [`docs/office-ide/HOSTING-ADAPTER.md`](office-ide/HOSTING-ADAPTER.md), [`docs/office-ide/PROCESS-MINING.md`](office-ide/PROCESS-MINING.md), [`docs/office-ide/MULTI-TENANT.md`](office-ide/MULTI-TENANT.md), [`docs/office-ide/REAL-ESTATE-VERTICAL.md`](office-ide/REAL-ESTATE-VERTICAL.md), [`docs/office-ide/BEDROCK-DEFERRED.md`](office-ide/BEDROCK-DEFERRED.md), [`librechat/README.md`](../librechat/README.md), [`infrastructure/docs/LIBRECHAT-HOSTING.md`](../infrastructure/docs/LIBRECHAT-HOSTING.md), [`mcp-plugins/README.md`](../mcp-plugins/README.md), [`process-engine/README.md`](../process-engine/README.md), [`conversation-mining/README.md`](../conversation-mining/README.md).

**Phase 0/1 delivered (code):** LibreChat config scaffold; FastAPI adapter (`teams-bot/web/`) with `/v1/models` + `/v1/chat/completions` SSE, bearer auth, history from request, `reasoning_content` status, `RAG_TURN_AUDIT` `channel=web`; unit tests in `test_openai_compat_web.py`.

**Phase 2 scaffolding (milestone, 2026-07-19):** Additive Terraform stubs — `infrastructure/librechat.tf` (ACA environment + LibreChat container app, ingress placeholders, commented Mongo Cosmos vCore + RAG adapter app), variables/outputs gated by `librechat_enabled = false`, hosting guide [`LIBRECHAT-HOSTING.md`](../infrastructure/docs/LIBRECHAT-HOSTING.md). **Not applied.** Still need human: Entra OIDC app registration, Mongo choice (Cosmos vCore vs Atlas), soft-fork image/ACR, then `terraform plan`/`apply` via deployment-ops (dev first).

**Phase 3 scaffolding (milestone, 2026-07-19):** [`mcp-plugins/`](../mcp-plugins/) — streamable-HTTP-shaped stdlib template, scope policy (`read`/`search`/`draft` / never-`send` v1), `MCP_TOOL_AUDIT` helper, SharePoint + Teams tool stubs (no live Graph), LibreChat example [`librechat/mcp-servers.example.yaml`](../librechat/mcp-servers.example.yaml). Onyx CE harvest documented only (no code copy). **Next for real Graph:** Entra app + admin consent (delegated OBO for user browse; optional `Sites.Selected` per task **35** for headless write).

**Phase 4 scaffolding (milestone, 2026-07-19):** [`process-engine/`](../process-engine/) — Pydantic process schema (inputs + `rag_query`/`plugin_call`/`llm_transform` steps + email-draft `never_send`), versioned filesystem catalog, dry-run runner with mocked callouts, example process `standard_client_reply@1`, MCP tool stubs `list_processes` / `run_process` (also thin wrappers under [`mcp-plugins/mcp_plugins/processes/`](../mcp-plugins/mcp_plugins/processes/)). Unit tests for schema + dry-run. **No deploy.** Next: wire real RAG/plugin clients; conversational parameter collection; expose via curated LibreChat agent.

**Phase 5 mining scaffolding (milestone, 2026-07-19):** [`docs/office-ide/PROCESS-MINING.md`](office-ide/PROCESS-MINING.md) + [`conversation-mining/`](../conversation-mining/) — offline `RAG_TURN_AUDIT` fixture → clustered candidate process sketches (compatible with process-engine promote flow); privacy/retention notes; unit tests. **No live KQL/Mongo.** Frontend gate remains documented in [`FRONTEND-EXIT-CRITERIA.md`](office-ide/FRONTEND-EXIT-CRITERIA.md) (decide go/no-go when document-IDE UX is required).

**Phase 6 scaffolding (milestone, 2026-07-19):** Outlook + Salesforce MCP plugin stubs (`mcp-plugins/mcp_plugins/outlook/`, `salesforce/`) — read/search/draft + never-send for mail; CRM lookup placeholders; LibreChat [`mcp-servers.example.yaml`](../librechat/mcp-servers.example.yaml) entries. Docs: [`MULTI-TENANT.md`](office-ide/MULTI-TENANT.md) (`tenant_id`, per-client LibreChat, Pinecone namespaces, SaaS needs custom frontend, Entra per customer), [`REAL-ESTATE-VERTICAL.md`](office-ide/REAL-ESTATE-VERTICAL.md) (domain processes on flexible core; example lease packet / handover checklist — not implemented). **No live Graph/SF; no admin dashboard yet.**

**Deferred Bedrock track (documented, 2026-07-19):** [`BEDROCK-DEFERRED.md`](office-ide/BEDROCK-DEFERRED.md) — shell unaffected; fix GDPR plan embedding **one-model** rule (index ≠ query breaks retrieval); Claude Polish golden eval gate before cutover. Pointers to [`GDPR-MIGRATION-PLAN.md`](../infrastructure/docs/GDPR-MIGRATION-PLAN.md) + [`VECTOR-DB-COMPARISON.md`](../pinecone-pipeline/docs/VECTOR-DB-COMPARISON.md).

**Smoke-test checklist (human — do not mark ✅ until confirmed):**
1. **Adapter local** — run `teams-bot/web` OpenAI-compat facade; LibreChat (or curl) against `/v1/models` + `/v1/chat/completions` SSE; confirm `reasoning_content` status + `channel=web` audit.
2. **Golden parity (optional)** — spot-check a few golden questions vs Teams on same corpus/namespace.
3. **MCP stubs (optional)** — `python -m mcp_plugins.outlook.server` / `salesforce.server`; `tools/list` + denied send scope.
4. **Entra / ACA (later)** — OIDC tenant lock + app-role gate; `librechat_enabled` Terraform apply via deployment-ops (dev first) — not part of this scaffolding session.

**Verification:** Point LibreChat at local adapter; golden parity vs Teams deferred to smoke after user testing. Do **not** mark ✅ until user confirms.

---

### 38. Zakwaterowanie corpus (partner accommodation)

**Priority:** Medium

**Status:** 🔄 In Progress — Pinecone **`production`** indexed (201 vectors, 4 docIds, validated 2026-05-31); bot routing on **`release`** at **`711d7e5`** — **prod bot deploy + Teams smoke still open**. Corpus files not in git under `source_data/` (indexed operator-side; see [KB changelog](../knowledge-base/CHANGELOG.md)).

**Goal:** Add top-level corpus folder `Zakwaterowanie/` (4 documents); slug `zakwaterowanie` for bot routing; index to Pinecone **`v3`** (dev) and **`production`** (prod).

**Code:** `corpus_metadata.py`, `retrieval_filter.py` (`RetrievalScope.ZAKWATEROWANIE`), `folder_map_prompt.md`, `status_copy.py` — merged **`711d7e5`**.

**Done:** Pinecone `v3` + `production` (duplicate cleanup KB-2026-05-31-001); routing code on `release`.

**Still open:** `./scripts/deploy.sh prod` from `release` + deploy-log entry; commit or document corpus files in repo; prod Teams smoke.

**Verification:** Prod Teams — zakwaterowanie / SMS CRM / różnice najem vs zakwaterowanie; App Insights `corpusTopic=zakwaterowanie`.

---

### 34. Client feedback Wave 3 (clarify, composer, golden eval)

**Priority:** High

**Status:** ✅ Completed — merged to `main` / `release` at **`c639099`** (2026-05-28); dev + prod deploy.

**Investigation:** [acceptance-criteria.md](../.cursor/skills/bot-quality-evaluation/acceptance-criteria.md) · Golden: `teams-bot/logs/client_feedback_golden.txt`

**Goal:** Focused bot changes from May 2026 feedback (no full hybrid index migration in this wave).

**Rollback (2026-05-28):** Commits after `c639099` on `feature/client-feedback-investigation-2026-05` (24m retrieval hacks, retrieval v2, extended folder map, structural clarify gate, clarification follow-up) were **reverted** — insufficient without broader architecture work. See [CLIENT-FEEDBACK-ARCHITECTURE-CHANGES.md](../teams-bot/docs/CLIENT-FEEDBACK-ARCHITECTURE-CHANGES.md#rollback-2026-05-28).

**Delivered / in branch:**
- **Clarification gate (B4, A9, A13):** `clarification_needed` + `clarification_questions` (max 2) on [`RAGStrategy`](../teams-bot/rag/optimizer.py); `respond_clarify` path in [`graph.py`](../teams-bot/rag/graph.py) / [`teams_entry.py`](../teams-bot/rag/teams_entry.py) — no Pinecone when clarifying. **LLM-only** (no regex/word-pattern fallback); topic-specific questions from optimizer prompt.
- **Answer composer (B2, B3):** [`answer_composer.py`](../teams-bot/rag/answer_composer.py) — optimizer-driven `answer_topic` + `numeric_answer_first` (no regex); topic blocks wired in [`nodes.py`](../teams-bot/rag/nodes.py) / [`teams_entry.py`](../teams-bot/rag/teams_entry.py).
- **Eval:** [`test_client_feedback_golden.py`](../teams-bot/tests/test_client_feedback_golden.py); manual repro via [`run_local_rag_tests.py`](../teams-bot/scripts/run_local_rag_tests.py); KQL [`prod_client_feedback_misroute.kql`](../scripts/kql/prod_client_feedback_misroute.kql).
- **Corpus checklist:** [CLIENT-FEEDBACK-CORPUS-REMEDIATION.md](../pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md) (P0 files, reindex steps).
- **Procesy deck removed (2026-05-28):** corpus file + Pinecone `v3`/`production` + handbook/anchor/prompts — commit `d134463`; ops log in [CLIENT-FEEDBACK-CORPUS-REMEDIATION.md](../pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md#procesy-deck-removal-2026-05-28--done).
- **RFC stub:** task **28** (hybrid search) — see [VECTOR-DB-COMPARISON.md](../pinecone-pipeline/docs/VECTOR-DB-COMPARISON.md).

**Verification (2026-05-28):** Dev smoke on **`c639099`** passed; merged to `main`/`release` and deployed prod. Confirm **no** `Procesy_ NW RENT_pl 2025.pptx` in `retrieved_documents` after Procesy removal. Colloquial 24m / early-termination routing remains **deferred** (architecture — task **28**, RFC).

- **Retrieval score ranking (2026-05-28):** anchor + primary merged by Pinecone score (not anchor-first); default `MAX_RAG_CONTEXT_CHARS=48000`; answer prompt — prefer higher trafność, surface cross-document conflicts + clarify when history ambiguous.
- **Handbook direct off (2026-05-28):** default `RAG_HANDBOOK_DIRECT_ENABLED=0`; optimizer no longer routes to `direct_mode=handbook` — Instrukcja via anchor + full RAG only.
- **Contract routing map (2026-05-28):** extended `folder_map_prompt.md` (N/W/R catalog, subfolder prefixes); router prompt — optimized_query current turn only; composer blocks CONTEXT-only (no embedded fee amounts).

**Deferred:** Hybrid Pinecone index migration, freshness metadata rerank, optimizer `alpha` per query; other P0 corpus items (Wzór I vs Przedłużenie caps) per remediation doc.

---

### 36. Extend RAG_TURN_AUDIT for conversation context forensics

**Priority:** Medium

**Status:** 🔄 In Progress — **P1/P2 shipped prod** (2026-05-28, **`c639099`**); **P3** (`retrieval_scores`, excerpt/content hashes) + KQL `prod_rag_context_by_conversation.kql` still open

**Goal:** Make prod logs sufficient to answer “which documents and chunks were used for this conversation” without re-fetching Pinecone.

**Requirements (from investigation):**
- **P1:** `conversation_id` (Teams thread) in audit payload
- **P1:** `response_path`: `rag` | `clarify` | `handbook` | `smalltalk`
- **P1:** `clarification_needed`, `clarification_questions` (when clarify gate fires)
- **P2:** `context_chunk_ids` or list of `docId:chunkIndex` actually sent to LLM (post `MAX_RAG_CONTEXT_CHARS` trim)
- **P2:** `sectionTitle` per source in compact `retrieved_documents`
- **P3:** optional `retrieval_scores` for top-k
- **P3:** optional short context excerpts or content hashes (document size limits)

**Implementation notes:**
- Extend [`teams-bot/rag/request_audit.py`](../teams-bot/rag/request_audit.py) `log_rag_turn_audit` and `StreamingResult` / [`function_app.py`](../teams-bot/function_app.py) call site
- Wire fields from [`teams_entry.py`](../teams-bot/rag/teams_entry.py), [`graph.py`](../teams-bot/rag/graph.py), [`nodes.py`](../teams-bot/rag/nodes.py)
- Add KQL: [`scripts/kql/prod_rag_context_by_conversation.kql`](../scripts/kql/prod_rag_context_by_conversation.kql) (group by `conversation_id`)

**Related:** task **34** (Client feedback), [acceptance-criteria.md](../.cursor/skills/bot-quality-evaluation/acceptance-criteria.md)

**Shipped (P1/P2):** `conversation_id`, `response_path`, clarify fields, `context_chunk_ids`, `sectionTitle` in compact `retrieved_documents` — wired in `request_audit.py` / `graph.py` / `function_app.py`.

**Verification:** Prod App Insights — one Teams thread with 3 turns grouped by `conversation_id`; add KQL helper when P3 scope is picked up.

---

### 37. Incremental Pinecone reindex (changed files only)

**Priority:** Medium

**Status:** 🔄 In Progress — manual selective path used for Instrukcja kaucja (2026-05-29); auto change-detection not implemented

**Goal:** After corpus edits, re-chunk and upsert **only affected documents** — not the full `source_data/` tree (~270 files).

**What we did (Instrukcja 2026-05-29):** **Selective reindex only** — two paths via [`pinecone-pipeline/scripts/reindex_files.py`](../pinecone-pipeline/scripts/reindex_files.py):

- `5 Instrukcje/Instrukcja dla nowego pracownika 2025.docx`
- `5 Instrukcje/Instrukcja dla nowego pracownika 2025.pdf`

Old Pinecone vectors for prior `docId`s were deleted first (`delete_corpus_document.py`). **No full-corpus** `ragstone-index` run.

**Gap:** Default [`cli.py`](../pinecone-pipeline/cli.py) / `ragstone-index` still **lists every supported file** under `DOCS_DIR`. With `SEND_TO_PINECONE=1`, cached files are skipped for parsing but **still upserted** to Pinecone — slow and wasteful for small edits.

**Requirements:**
- **CLI:** `ragstone-index --only <relative-path>…` and/or `--changed-since <git-ref|timestamp>` to limit parse + upsert scope
- **Change detection:** use `mtime` vs JSONL cache (already in `is_cache_fresh`) + optional git diff on `source_data/`
- **Delete-before-upsert:** when `docId` changes (file replaced), call `delete_corpus_document.py` logic for old id before upsert
- **Docs:** operator checklist in [CLIENT-FEEDBACK-CORPUS-REMEDIATION.md](../pinecone-pipeline/docs/CLIENT-FEEDBACK-CORPUS-REMEDIATION.md) — prefer `reindex_files.py` until `--only` lands
- **Docker:** `docker compose -f docker-compose.pinecone.yml run --rm pinecone-indexer uv run python scripts/reindex_files.py --force "path/under/source_data"`

**Related:** task **13** (upload automation), [pinecone-pipeline/README.md](../pinecone-pipeline/README.md)

**Verification:** Edit one small `.docx`; run incremental path only; confirm Pinecone vector count delta ≈ that file's chunks (+ summaries), not full corpus

---

### 25. Teams bot access control (display name allowlist + no group chats)

**Priority:** High

**Status:** 📋 To Do

**Goal:**
Limit who can use the Teams bot during rollout and avoid unsupported contexts without calling the LLM.

**Requirements:**
- **Allowlist by Teams display name** (`from.name` / `teams_user_name`): configurable list (e.g. env var with comma‑separated names). If the sender’s display name is **not** on the list, respond with a **fixed Polish placeholder** explaining that the bot is in a testing phase and access is restricted — **do not** run optimize/retrieve/LLM.
- **Group chats and channels:** if `is_group_chat` is true, **always** reject the same way (no LLM): respond with a **fixed Polish message** that group/channel chats are not supported yet (wider copy is fine).
- **Order of checks:** resolve group/non‑group first, then allowlist for 1:1 chats.
- **Docs:** document env var name(s), matching rules (e.g. trim / case‑insensitive), and that display names are not as stable as AAD object IDs or email.

**Implementation notes:**
- Early exit in `process_message` (before RAG/graph) using `send_simple_reply` or equivalent; reuse or mirror patterns in `teams-bot/function_app.py` and `teams-bot/bot/activity_handler.py`.
- Optional: structured log line for “access denied” with reason (`group_chat` vs `not_in_allowlist`) without logging full message bodies.

---

### 26. Teams streaming: 2‑minute limit, pacing, and 403 diagnostics

**Priority:** Medium

**Status:** 🔄 In Progress — prefix-extension / invalid-cumulative-text fixed (`b279fc3`); `ContentStreamNotAllowed` vs user-stop split (`c83317b`); remaining 403 causes (2‑min timeout, message size) + structured App Insights logging still open

**Problem / context:**
Microsoft’s [Stream bot messages](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/streaming-ux) doc states that if the bot does **not** finish the streaming process in time, Teams returns **`403` / `ContentStreamNotAllowed`** with **`Content stream finished due to exceeded streaming time.`** — a **strict two‑minute** limit on the streaming session. Other **`403`** cases include user **Stop**, message too large, invalid cumulative stream text, stream already completed, etc.

**Root cause closed (2026-04, branch `feature/client-feedback-paragraph-split-2026-04`):** the most frequent `ContentStreamNotAllowed` we were hitting was the **invalid cumulative stream text** flavour — `rag.citations.remap_inline_citation_numbers` rewrote inline `[Źródło N]` indices during post-process so the final `send_final` was **not** a strict prefix-extension of the live token chunks. That regression was first masked by `eb3836e` (two-chunk authoritative reveal, no per-token streaming) and then properly fixed by `b279fc3`: a CONTEXT-index → display-row map is **precomputed at retrieval time** from `work.sources` in [`teams-bot/rag/citations.py`](../teams-bot/rag/citations.py) (`precompute_streaming_citation_map`), shared across the live token loop (`streaming_safe_remapped_text` with `_truncate_unclosed_inline_bracket` / `_truncate_partial_citations_used_line` to keep the visible buffer monotonic) and the final `send_final`, so every activity in the same stream derives from the same renumbered string by construction. `function_app.py` retains a `StreamingProtocolError` safety net that ships the answer as one `send_message` if Teams ever rejects a chunk again. 22 new unit tests in `tests/test_streaming_citation_remap.py` lock the prefix-extension invariant.

**Observed gap (still open):**
- After `c83317b`, **`ContentStreamNotAllowed`** maps to `StreamingProtocolError` (fallback path); other **`403`** codes still become `StreamingStoppedError("User stopped the stream")`, which **hides** Teams 2‑minute timeout, message-too-large, stream-already-completed.
- Long turns (RAG + LLM + many chunks) can still approach or exceed the platform 2‑minute streaming limit; this may surface as **“Ta odpowiedź została zatrzymana”** in Teams even when the model finished.

**Goal:**
- **Document** the 2‑minute streaming limit and **1 POST/s** throttling in bot/deployment docs as operational constraints.
- **Log** Bot Framework error **body** / code (without secrets) so App Insights distinguishes **timeout** vs **user stop** vs **size / sequence** errors (currently we only distinguish `StreamingProtocolError` vs `StreamingStoppedError`).
- **Design** mitigations for answers that routinely run long: e.g. faster path to `final` message, fewer intermediate streaming activities, proactive / ack‑early patterns where appropriate, or product copy when the stream is cut by Teams.

**Deliverables:**
- Short implementation in `streaming.py` + `function_app.py` (or adjacent) for structured failure logging; optional follow‑up task split if scope grows.

---

### 28. Hybrid search on Pinecone (sparse + dense, BM25 lane)

**Priority:** Medium

**Status:** 📋 To Do — design ready

**Design doc:** task **28** below; vendor context in [`../pinecone-pipeline/docs/VECTOR-DB-COMPARISON.md`](../pinecone-pipeline/docs/VECTOR-DB-COMPARISON.md)

**Goal:** Add a sparse / BM25 retrieval lane alongside today's dense embeddings to improve recall on Polish queries that contain literal terms (surnames, document codes, abbreviations like "OWU", named programs like "NORTHWIND CLUB", section references). Stay on Pinecone; reuse existing namespaces, ID scheme, metadata filters, and citation pipeline.

**Why now:** Vector-only search misses exact-keyword queries today. Hybrid is the lowest-blast-radius improvement available without changing vendors or chunking. Design details are in task **28** (this file).

**Approach (phase 1):**
- Sparse encoder: `pinecone-text` BM25Encoder + a Polish-aware tokenizer; SPLADE deferred as upgrade path.
- New Pinecone index with `metric="dotproduct"` (cosine indexes cannot accept `sparse_values`). Dual-write during migration; trivial rollback by env var.
- Bot retriever calls Pinecone with both vectors in one round-trip; metadata filters in [`teams-bot/rag/retrieval_filter.py`](../teams-bot/rag/retrieval_filter.py) unchanged.
- Score fusion via `pinecone-text.hybrid_convex_scale` with a fixed `HYBRID_ALPHA_DEFAULT` for phase 1.

**Phased TODO:**
- **Phase 0 — Spike:** pick Polish tokenizer (Morfologik vs lightweight stemmer); offline compare dense vs sparse vs hybrid top-10 on ~20 known-painful queries; decide encoder hosting (Azure Blob vs baked) and refit trigger.
- **Phase 1 — Indexer:** `fit_bm25_encoder.py` script; `chunk_output/*.bm25_sparse.jsonl` cache; new env vars (`PINECONE_INDEX_NAME_HYBRID`, `BM25_ENCODER_PATH`, `HYBRID_ALPHA_DEFAULT`); `ensure_index` creates dotproduct index; `build_vectors_from_objects` attaches sparse vectors.
- **Phase 2 — Bot:** encoder loader (cold-start fetch + module cache); hybrid Pinecone call in [`teams-bot/rag/nodes.py`](../teams-bot/rag/nodes.py); per-turn alpha logging.
- **Phase 3 — Validation and rollout:** re-run [corpus-qa-evaluation.md](../.cursor/skills/bot-quality-evaluation/corpus-qa-evaluation.md) against dev hybrid; promote production with dual-write for one reindex cycle; decommission cosine after 2-week soak.
- **Optional follow-up:** add `alpha: float` to `RAGStrategy` so the optimizer can push toward keyword vs meaning per query; re-evaluate SPLADE if BM25 recall plateaus.

**Open questions / risks:** encoder hosting (blob vs baked), refit cadence/trigger, Polish tokenizer footprint inside the Functions image, summary routing vectors likely stay dense-only, Function App cold-start delta when fetching encoder JSON.

**Related:** task **16** (retrieval quality), task **20** (knowledge base architecture), task **24** (folder/file-aware retrieval). Vendor comparison context in [`VECTOR-DB-COMPARISON.md`](VECTOR-DB-COMPARISON.md).

**Client speed feedback (2026-04):** perceived “Ctrl+F is faster” overlaps with **task 32** (Teams token streaming / TTFT) and this hybrid retrieval work — track both in the same App Insights latency baseline.

---

### 29. Answer style overhaul (paraphrase, flexible length, TL;DR, neutral tone)

**Priority:** High

**Status:** ✅ Completed — wdrożone dev + prod (2026-05); użytkownik potwierdził działanie w Teams

**Goal:** Reduce verbatim copy-paste from chunks; keep answers flexible (short vs long); long answers include a bottom-line **TL;DR** where required; neutral “rzeczowy” tone (no extra small talk).

**Implementation (2026-04):** [`teams-bot/rag/prompts.py`](../teams-bot/rag/prompts.py) — paraphrase rules, TL;DR rules for `standard` (long) / `detailed`, concise ~60 words cap; [`teams-bot/rag/optimizer.py`](../teams-bot/rag/optimizer.py) — `answer_depth` guidance biased to `concise` for follow-ups.

**Update (2026-05, branch `feature/sharepoint-links-and-style-2026-05`):** explicit ban on cross-language acknowledgment / “confirmed” / “thanks” filler; `standard` + `detailed` require a bold **Najważniejsze punkty** (or **Key points** when answering in English) bullet block for long answers (~120+ words); Markdown bold for key terms; see task **33** for per-user `/style` preferences.

**Verification:** Polish corpus QA + Teams smoke; confirm no wall-of-raw-chunk pastes.

---

### 27. Latency optimization round 1 (lean Teams path)

**Branch:** `feature/latency-fix-notes-cleanup` → merged to `release` (2026-04-17).

**Status:** ✅ Completed

**Related:** tasks **17** (observability / phase timings), **22** (status UX), **23** (citations latency follow-up), **32** (token streaming TTFT follow-up: `orchestration_first_model_token`, throttled `send_chunk` path).

**Goal:** Remove the outer Deep Agent from the Teams hot path, reduce TTFT (smaller RAG context cap, Pinecone client reuse, optional pre-warm), add finer-grained Teams status lines during pre-token work, and document latency baselines.

**Done (summary):** Outer Deep Agent removed (`teams_entry`); `reasoning_effort=minimal` on answer + optimizer `ChatOpenAI`; slim `RAGStrategy` + shorter optimizer prompt / folder map; dev measured ~24s → ~2.5s optimize segment; parallel **anchor** retrieval for two fixed Instrukcje handbook paths; citation UX (`should_attach_source_block` false positive on „nie znalazłem…”, inline `CITATIONS_USED` alignment, same-doc comma collapse); status text no longer shows raw `chunks_only`; Table Storage history cache + limits; tests for memory / citations / anchor.

**Phase 0 — baseline (operator, before/after deploy):**

1. In Log Analytics for **`appi-northwind-dev`**, run:
   - [`scripts/kql/turn_latency_by_trace.kql`](../scripts/kql/turn_latency_by_trace.kql) (set `trace_id` from a slow turn).
   - Query slow turns: `traces | where timestamp > ago(7d) | where message startswith "TEAMS_TURN_LATENCY "` | extend j=parse_json(substring(message, 18)) | where tostring(j.step) == "turn_complete" | project timestamp, j | order by timestamp desc | take 20` then join steps by `trace_id`.
2. Record per slow turn (wall): `inner_rag_optimize_complete.segment_ms`, `inner_rag_retrieve_complete.segment_ms`, `inner_rag_respond_complete.segment_ms`, `orchestration_authoritative_stream_*`, and `teams_entry_*` (legacy traces may still show `deep_agent_outer_stream_*`).
3. Note Function App settings: **`SUMMARY_RETRIEVAL_ENABLED`**, **`RAG_NEIGHBOR_EXPANSION_ENABLED`** (expect `0` / off for latency baseline).

**Baseline table (fill from App Insights):**

| Turn (trace_id / date) | optimize_ms | retrieve_ms | respond_ms | teams_entry_ms | total_wall_s | Notes |
|------------------------|-------------|-------------|------------|------------------------|--------------|-------|
| _pending_              |             |             |            |                        |              |       |

**Phase 5 — deploy & measure:** `./scripts/deploy.sh dev` (repo root; see **deployment-ops** skill). Re-run the Phase 0 KQL; append a second table with the same columns for ~5 fresh turns. Smoke-test in Teams (1:1). Set this task to `Completed` only after you confirm testing passed.

**Phase 2.5 — retrieval flags (verify in Azure Portal):** on **dev** and **prod** Function Apps → **Configuration**, confirm `SUMMARY_RETRIEVAL_ENABLED` and `RAG_NEIGHBOR_EXPANSION_ENABLED` are unset or `0` unless you intentionally accept the extra Pinecone round-trips. Record actual values in the baseline table.

---

### 5. Add SharePoint Deep Links to Citations

**Status:** 🔄 In Progress — ✅ shipped **dev + prod** (`1ce0469`, 2026-05-08); smoke OK — **operator verification** of full SharePoint ↔ Pinecone path coverage still open

**Current behavior:** [`teams-bot/rag/prompts.py`](../teams-bot/rag/prompts.py) — model **nie** dodaje ``[Źródło N]``; CONTEXT ma nagłówki **Fragment N**. Lista **Źródła** z linkami budowana jest w kodzie z pobranych dokumentów (`precompute_streaming_citation_map` + `format_citations_from_display_rows`), z pominięciem przy typowych frazach „brak w dokumentacji” (`should_attach_source_block`). Stream: `streaming_safe_answer_visible_text`. Przy błędzie strumienia: `delete_stream_activity` przed fallback `send_message`. User-facing PL: [`BOT-USAGE-PL.md`](../docs/customer-support/BOT-USAGE-PL.md).

**Implementation milestone (2026-05):** jedna pozycja **Źródła** na plik, złączone strony w etykiecie; PDF bez `?page=` w URL; Office z `?web=1` dla podglądu w przeglądarce.

**Deferred (not investigated):** SharePoint / Teams **page-level** or in-document deep links (e.g. opening a PDF at a given page reliably in the embedded client). Tracked here as product/tech follow-up only when the client supports it.

**Done / shipped:**
- Bot-side URL resolution and markdown **Źródła** list with anchored links; Teams activities use `textFormat: markdown` for clickable links.
- Terraform: `sharepoint_library_base_url` in [`infrastructure/environments/dev.tfvars`](../infrastructure/environments/dev.tfvars) / [`prod.tfvars`](../infrastructure/environments/prod.tfvars) → Function App `SHAREPOINT_LIBRARY_BASE_URL` (`AI/dev` vs `AI/prod` under `Shared Documents`).
- Example local values in [`teams-bot/local.settings.json.example`](../teams-bot/local.settings.json.example) and [`.env.example`](../.env.example).
- Operator sync script: [`scripts/kb/sharepoint_sync.py`](../scripts/kb/sharepoint_sync.py) + [`scripts/kb/sharepoint_sync_requirements.txt`](../scripts/kb/sharepoint_sync_requirements.txt) (upload `source_data` under `AI/<dev|prod>/`).

**Operator guide:** [citation-sharepoint-links.md](../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md) — how links resolve, path alignment, and where to change settings.

**Still to verify:** corpus uploaded to SharePoint paths matching Pinecone `sourceRelativePath`; `terraform apply` applied so dev/prod Function Apps have the expected base URL; Teams smoke-test every citation link opens the correct file.

**Optional next reindex:** set `SHAREPOINT_BASE_URL` in pipeline so Pinecone rows include baked `sharepointUrl` metadata (bot already prefers it when present).

---

### 33. Per-user answer preferences (`/style`)

**Priority:** Medium

**Status:** ✅ Completed — wdrożone dev + prod (2026-05); opis dla użytkowników: [`BOT-USAGE-PL.md`](../docs/customer-support/BOT-USAGE-PL.md)

**Goal:** Let users persist free-text style instructions (tone, length, language) without polluting chat history; inject into the answer model system prompt.

**Implementation:**
- Azure Table **`userpreferences`** — [`teams-bot/rag/user_preferences.py`](../teams-bot/rag/user_preferences.py) (`PartitionKey` = Teams user id, `RowKey` = `style`, `preferenceText`); same storage account as conversations.
- [`teams-bot/function_app.py`](../teams-bot/function_app.py) — `/style`, `/styl` (get / set / `reset`); early exit before RAG.
- [`teams-bot/rag/graph.py`](../teams-bot/rag/graph.py) — load block into `ChatState` / Teams pipeline `initial_state`; [`teams-bot/rag/prompts.py`](../teams-bot/rag/prompts.py) + [`teams-bot/rag/nodes.py`](../teams-bot/rag/nodes.py) — `{user_preferences_block}` on RAG, handbook, and direct paths.
- Env: `USER_PREFERENCES_MAX_CHARS` (default 2000) in [`teams-bot/local.settings.json.example`](../teams-bot/local.settings.json.example).

**Verification:** `/style krótko`, ask a question, `/style reset`; confirm `WELCOME_MESSAGE` lists the command.

---

### 35. Bot SharePoint write access via Graph `Sites.Selected`

**Priority:** Medium

**Status:** 📋 To Do — design recorded; awaiting tenant admin actions before any bot Graph code

**Goal:** Give the Teams bot its own narrow **read/write** access to the `Northwind-AI` SharePoint site so it can list, download, and upload corpus or draft files **without** a user-delegated token (headless, 24/7).

**Chosen approach:** Application permissions on the existing bot AAD app — **`Sites.Selected`** (not `Sites.ReadWrite.All`). Requires **admin consent** for the permission, then a **per-site** grant of `write` for this app on `https://contoso.sharepoint.com/sites/Northwind-AI` only.

**Rationale (short):** `Sites.ReadWrite.All` is tenant-wide (usually rejected). Delegated/OBO with a human account does not give the bot independent access when the user is offline.

#### Engineering (what we do after admin grants)

1. New module `teams-bot/integrations/sharepoint.py` — `SharePointClient` with `list_folder`, `download_file`, `upload_file` (explicit path allowlist under `AI/`; no arbitrary delete).
2. MSAL **client credentials** → `https://graph.microsoft.com/.default`; reuse `MICROSOFT_APP_ID` / `MICROSOFT_APP_PASSWORD`.
3. Resolve `site-id` and default document **drive id** once at startup; cache.
4. Expose only behind a feature flag `BOT_SHAREPOINT_TOOLS_ENABLED=0` and a future sub-workflow / tool registry (task **14c**); never on every RAG turn.
5. Structured audit log line `SHAREPOINT_TOOL_AUDIT` (operation, relative path, bytes, HTTP status — no file body).
6. Unit tests with mocked Graph HTTP.

#### Admin actions required (copy to tenant admin)

1. **App to use:** the existing Teams bot application (Application (client) ID = `MICROSOFT_APP_ID` from the Function App / Key Vault).
2. In **Azure Portal** → **Microsoft Entra ID** → **App registrations** → that app → **API permissions** → add **Application** permission **Microsoft Graph → Sites.Selected** → **Grant admin consent** for the tenant.
3. Grant this application **write** on site `https://contoso.sharepoint.com/sites/Northwind-AI` only. Example (Graph Explorer as SharePoint admin, or PowerShell with `Connect-MgGraph`):

   ```http
   POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions
   Content-Type: application/json

   {
     "roles": ["write"],
     "grantedToIdentities": [
       { "application": { "id": "<MICROSOFT_APP_ID>", "displayName": "Northwind Residences Bot" } }
     ]
   }
   ```

   Resolve `{site-id}` once: `GET https://graph.microsoft.com/v1.0/sites/contoso.sharepoint.com:/sites/Northwind-AI` → use the `id` property.

4. **Reply to engineering** with confirmation that steps 2–3 succeeded and the `id` string if helpful for smoke tests.

#### Verification (engineering, after admin)

- Smoke script or one-off: list `AI/v3`, download one known file, upload a small test file under `AI/v3/.smoke-test/` then remove it.
- Enable `BOT_SHAREPOINT_TOOLS_ENABLED=1` in **dev** only after smoke passes; then prod.

**Related:** task **14c** (broader M365 Graph integrations), task **5** (citation deep links).

---

### 8. Admin Dashboard

**Status:** 📋 To Do

- Document upload interface
- Usage analytics
- Configuration management

---

### 9. Clear Bot History When User Deletes Teams Chat

**Status:** 📋 To Do — **partial:** user command **`/clean_chat_history`** (aliases) shipped **`d216100`**; auto-on-Teams-delete not built

**Problem:**
Bot stores conversation history in Azure Table Storage independently from Teams. When a user deletes their Teams chat, the bot still retains all conversation history and continues to "remember" previous conversations.

**Expected Behavior:**
When a user deletes their chat in Teams, the bot should also clear its stored conversation history for that user, giving them a fresh start.

**Done (manual reset):** `/clean_chat_history`, `/wyczysc_historie` in `function_app.py` — clears `conversations` + `conversation_context` for the user.

**Investigation Needed:**
- Determine if Teams sends a `conversationUpdate` or `deleteUserData` activity when chat is deleted
- If not, rely on TTL (task **31**, `HISTORY_TTL_HOURS`) or expand user-facing reset copy

**Implementation Notes:**
- `TableStorageMemory.clear_history(user_id)` method already exists
- Hook into Teams delete events if the platform exposes them

---

### 11. Azure Marketplace Deployment

**Status:** 📋 To Do

**Goal:**
Investigate deploying RAGStone to Azure Marketplace so customers can add it to their environment with minimal setup.

**Investigation Areas:**
- Azure Marketplace publishing requirements and process
- ARM templates / Azure Resource Manager for one-click deployment
- Managed Application vs Solution Template approach
- Licensing models available (BYOL, free, per-user)
- Certification requirements for marketplace listing
- Integration with existing Terraform infrastructure

**Expected Benefits:**
- Simplified customer onboarding (no manual setup process)
- Discoverability through Azure Marketplace
- Built-in billing integration options

---

### 12. Full Azure/EU Migration & GDPR Compliance

**Status:** 📋 To Do

**Authoritative write-up:** [GDPR Migration Plan](../infrastructure/docs/GDPR-MIGRATION-PLAN.md) — target EU architecture, embedding/LLM direction, and compliance themes. **Vector store options:** [Vector DB Comparison](../pinecone-pipeline/docs/VECTOR-DB-COMPARISON.md).

**Goal (summary):**
Move toward EU-resident processing and GDPR-aligned controls. The linked migration plan is the source of truth for the evolving target stack (e.g., Azure OpenAI vs AWS Bedrock, local embeddings, vector DB choice).

**Themes to track (detail in linked docs):**
- Data residency, DPA, consent, erasure, retention, audit logging
- Terraform, `teams-bot`, and `pinecone-pipeline` changes coordinated with the chosen architecture
- Customer-facing privacy / GDPR documentation

**Migration checklist (high level):**
- [ ] Finalize target architecture per [GDPR Migration Plan](../infrastructure/docs/GDPR-MIGRATION-PLAN.md)
- [ ] Choose vector store path per [VECTOR-DB-COMPARISON.md](../pinecone-pipeline/docs/VECTOR-DB-COMPARISON.md)
- [ ] Update infrastructure and application code for the chosen stack
- [ ] Re-index if embedding model or index dimensions change
- [ ] Document compliance measures and customer DPA templates as needed

---

### 17. Observability: dependency health checks & richer logging

**Status:** 📋 To Do

**Goal:**
Make production (and dev) incidents faster to diagnose by surfacing **whether critical dependencies are reachable and correctly configured**, not only “the Function App returned 500.” Pinecone, OpenAI, and Azure Table Storage are **examples**; coverage should be deliberate and broader.

**Why (examples only — expand in design):**
- **Pinecone:** wrong API key, index name, namespace, or outage → empty retrieval or errors deep in the graph.
- **OpenAI:** quota, model name mismatch, regional block → optimizer or chat fails with generic messages.
- **Azure Table Storage:** connection string / RBAC → memory load/save fails silently or with obscure exceptions.
- **Bot Framework / Teams:** token or messaging endpoint issues → replies never arrive despite RAG succeeding.

**Planned design work (do before large implementation):**
1. **Inventory call sites** — Map every external dependency in `teams-bot/` (and optionally `pinecone-pipeline/`): REST clients, SDKs, env vars used, and failure modes (timeout vs 401 vs empty result).
2. **Classify signals**
   - *Liveness:* can we complete a minimal authenticated call? (e.g. Pinecone `describe_index_stats` or a 1-vector dry query; OpenAI models list or tiny embedding; storage list tables or point read.)
   - *Configuration sanity:* required env vars present; index dimension vs embedding model; namespace matches tfvars.
   - *Runtime path:* optional structured fields on existing `RAG_TURN_AUDIT` (or sibling events) for “retrieval_ms”, “pinecone_error_code”, “openai_status”, without logging secrets.
3. **Where to expose**
   - Extend **`/api/health`** (or add **`/api/health/ready`**) with dependency sub-checks: return 200 with JSON body listing `ok` / `degraded` per dependency, or 503 if critical path is down (define which are critical vs optional, e.g. memory off vs on).
   - **Application Insights:** one trace or custom metric per check on a schedule (Timer Trigger) or on cold start — avoid hammering APIs; cache results with TTL (e.g. 60s).
   - **On-demand admin** — optional secured endpoint or pipeline CLI flag for pre-flight before deploy.
4. **Security & cost** — No secrets in logs; redact URIs; rate-limit checks; document cost impact of embedding-based probes.
5. **Alerting (later)** — Azure Monitor alert rules on health endpoint or custom metrics when prod degrades.

**Deliverables:**
- Short **design note** (in `deployment-ops` skill / `reference.md` or new `docs/OBSERVABILITY.md`) listing dependency matrix and chosen probes.
- Code changes: health/ready implementation + structured logging improvements agreed in the design.

---

### 18. Production deployment log (changelog)

**Status:** 🔄 In Progress — entries through **2026-05-29** (`5684455` Instrukcja); append each future prod deploy (next expected: **`711d7e5`** Zakwaterowanie routing)

**Goal:**
Maintain a **single living document** that records **every production deployment** so anyone can see **when** prod changed, **what** shipped, and **how to correlate** issues with a release.

**Location:** [`docs/deployments/CHANGELOG.md`](deployments/CHANGELOG.md) (append via **deployment-ops** skill after prod deploy).

**Each entry should capture (template):**
- **Date / time (UTC)** and **who** ran the deploy (optional).
- **Git references:** at minimum **`release` branch commit SHA** (and **`main`** if different); optional **tag** or PR link.
- **Scope:** infra only, bot code only, or full stack (Terraform + app).
- **Notable changes:** bullet list of **features**, fixes, config (e.g. new App Insights, Pinecone namespace, model names).
- **Terraform / Azure:** note if `terraform apply` ran and any new resources.
- **Verification:** link or one-liner (e.g. health URL, smoke test in Teams).

**Process:**
- Append a new row or subsection **as part of the release checklist** after a successful prod deploy (same session as `scripts/deploy.cmd prod` or `./scripts/deploy.sh prod` on `release`).
- Backfill **recent history** from known releases (e.g. 2026-04 prod Log Analytics + bot deploy) when the file is created.

**Deliverables:**
- ~~Prod deploy changelog~~ ✅ — `docs/deployments/CHANGELOG.md`

---

### 13. Improve Pinecone Pipeline - Document Upload Automation

**Status:** ⏸️ On Hold

**2026 scope (merged via `feature/pinecone-pipeline-v3` → `main`):** Dockerized pipeline (`pinecone-pipeline/Dockerfile`), dual Pinecone namespaces via `PINECONE_NAMESPACE_DEV` / `PINECONE_NAMESPACE_PROD`, same index (`text-embedding-3-small`), corpus under `source_data/`, richer citation metadata (`sourceRelativePath`, block range), **`corpusTopic` / `corpus_metadata`**, **optional span summary vectors** (`summary_spans.py`, `GENERATE_SUMMARIES` on by default when `SEND_TO_PINECONE=1`), namespace validation script (`scripts/validate_pinecone_namespace.py`). Terraform tfvars + Function App settings for OpenAI chat models. SharePoint watch folders / Graph sync remain future work. OpenSearch/AWS deferred.

**References:**
- **Pipeline (CLI, config, formats):** [`pinecone-pipeline/README.md`](../pinecone-pipeline/README.md)
- **Manual RAG / citation QA:** ad hoc Polish questions and [`run_local_rag_tests.py`](../teams-bot/scripts/run_local_rag_tests.py) (`--question` / `--file`); expect grounded paths under `pinecone-pipeline/source_data/`.
- **Grounded chunk export + evaluation write-up:** [corpus-qa-evaluation.md](../.cursor/skills/bot-quality-evaluation/corpus-qa-evaluation.md)
- **Vector DB / hosting options:** [Vector DB Comparison](../pinecone-pipeline/docs/VECTOR-DB-COMPARISON.md)
- **EU / compliance context:** [GDPR Migration Plan](../infrastructure/docs/GDPR-MIGRATION-PLAN.md)

**Goal:**
Review and improve the document upload process in pinecone-pipeline to make it more automated and user-friendly.

**Current State:**
- Manual CLI-based document upload
- Requires technical knowledge to operate

**Investigation Areas:**
- Automated document ingestion from SharePoint/OneDrive
- Watch folder functionality for new documents
- Webhook triggers for document updates
- Batch processing improvements
- Progress tracking and status reporting
- Error handling and retry mechanisms
- Document versioning and update detection

**Potential Improvements:**
- SharePoint Graph API integration for automatic sync
- Scheduled jobs for periodic document refresh
- Admin UI for upload management (ties into Task #8 Admin Dashboard)
- Document change detection and incremental updates

---

### 16. RAG retrieval quality and citation faithfulness

**Status:** ⏸️ On Hold

**Investigation notes (2026-04-05, live Pinecone via `uv run` + `.env`):**
- **Index:** `text-embedding-3-small`, **dimension 1536**, **metric cosine**, **dense** vectors.
- **Namespaces:** `v3` **2187** vectors, `production` **2187** (aligned); legacy `v2` **1702**; **total_vector_count 6076**.
- **Local power company / VD probe (2026-04-05, pre–wider-k):** long query missed `6 Local power company/` in unfiltered top-15; shorter *"local power company VD1 VD2 …"* put VD2 at **rank 4**, VD1 at **9** — with **k≤6**, noise still dominated. **After merge:** **`num_documents` 10–20**, **summary-first**, **neighbor expansion** improve pool size; **rerank** still deferred.
- **Metadata filter spike:** Pinecone API returned **`$contains` / `$regex` not valid operators** for this index — substring path filters likely need **categorical fields at ingest** (`$eq` / `$in`) and/or **client-side post-filter** after a wider `top_k`.

**Context:**
Manual testing with ad hoc questions surfaced **retrieval and answer-quality gaps** even when the correct files exist under `pinecone-pipeline/source_data/`.

**Observed issues:**
- **Wrong-document retrieval:** e.g. questions about **the local power company** (`1 Najem Instytucjonalny/6 Local power company/`) and **pełnomocnictwa VD1/VD2** return chunks from unrelated **RODO / Najem F** PDFs (similar “tenant/legal” semantics, different topic).
- **Refusal paired with irrelevant sources:** the model states that documentation was not found while still listing citations that do not support the answer (undermines trust).
- **Corpus vs index drift:** citation filenames or dates may not match the current local `source_data/` tree if the Pinecone namespace was built from an older export; confirm **namespace** (e.g. `v3`) and re-index after corpus updates.
- **Path display:** UI may show Polish diacritics (`Załącznik`) while stored paths use ASCII (`Zalacznik`); not a functional bug but can confuse verification.

**Implementation (2026-04-05, updated same month):**
- **Pipeline:** [`pinecone-pipeline/corpus_metadata.py`](../pinecone-pipeline/corpus_metadata.py) — `corpusTopic` / `corpusTopFolder` = **slug pierwszego segmentu** ścieżki (layout `source_data`: Najem I, Najem F, VAT, rezerwacja, instrukcje, NORTHWIND CLUB); `corpusPathPrefix` = dwa pierwsze segmenty (np. the local power company jako `.../6_local_power_company`). Lista dokumentowych korzeni w `SOURCE_DATA_ROOT_SEGMENTS`; nowy folder na głównym poziomie → dopisać tam i dodać wartość w `RetrievalScope` bota.
- **Bot:** [`retrieval_filter.py`](../teams-bot/rag/retrieval_filter.py) — `corpusTopic` scope + chunk-row filter (`summaries` false / missing). [`optimizer.py`](../teams-bot/rag/optimizer.py) — `retrieval_scope`, **`retrieval_tier`** (`summary_then_chunks` | `chunks_only`), **`num_documents` 10–20**, osobny model **`OPENAI_OPTIMIZER_MODEL`**. [`nodes.py`](../teams-bot/rag/nodes.py) — summary stage → fetch span chunks → neighbor expansion → context cap; fallback bez filtra przy 0 wynikach; **`SUMMARY_RETRIEVAL_ENABLED`**. [`pinecone_ids.py`](../teams-bot/rag/pinecone_ids.py) — stabilne id chunków `{docId}:{chunkIndex:04d}`.
- **Citations:** [`prompts.py`](../teams-bot/rag/prompts.py) + [`citations.py`](../teams-bot/rag/citations.py) `should_attach_source_block` + [`function_app.py`](../teams-bot/function_app.py) — suppress **Źródła** block when the answer matches common Polish “not found” phrasing.
- **Audit / Azure logs:** [`teams-bot/rag/request_audit.py`](../teams-bot/rag/request_audit.py) — per-turn JSON trace `RAG_TURN_AUDIT` (user, messages, Pinecone index/namespace, metadata filter, retrieved paths, fallback flag). Terraform [`infrastructure/insights.tf`](../infrastructure/insights.tf) + Log Analytics workspace + `APPLICATIONINSIGHTS_CONNECTION_STRING` on the Function App.

**Observability status:** ✅ **Operational on dev** (2026-04-05): `terraform apply` + bot deploy completed; traces visible in Application Insights **`appi-northwind-dev`** → **Monitoring → Logs** (not Activity log). Example KQL: `traces | where message startswith "RAG_TURN_AUDIT" | order by timestamp desc`. **Prod:** run `terraform.sh prod apply` when ready so the prod Function App gets the connection string (and redeploy bot).

**Corpus QA pack + Pinecone probe (2026-04-06):** Six Polish questions grounded in chunks via [`generate_qa_pairs_from_corpus.py`](../pinecone-pipeline/scripts/generate_qa_pairs_from_corpus.py) (`--seed 42`), then [`run_local_rag_tests.py`](../teams-bot/scripts/run_local_rag_tests.py) and [`probe_pinecone_retrieval.py`](../teams-bot/scripts/probe_pinecone_retrieval.py). Weak spots historically: **duplicate language variants**, **narrow k**, **chunk boundaries** — mitigated in code by **wider k**, **summary-first**, **neighbors** (see [corpus-qa-evaluation.md](../.cursor/skills/bot-quality-evaluation/corpus-qa-evaluation.md)). **`teams-bot/rag/chain.py` removed**; only **`RAGGraph`** remains.

**Summary-first + deploy (2026-04, merged to `main`):** Pipeline upserts **`summaries=true`** span vectors (parallel `SUMMARY_*` envs); bot uses **`OPENAI_MODEL`** / **`OPENAI_OPTIMIZER_MODEL`** (Terraform app settings). Windows Docker: **`scripts/deploy.cmd`**, **`terraform.sh`** no longer passes `-var-file` to **`init`**. E2E: dev Teams + `RAG_TURN_AUDIT` in Application Insights.

**Next (retrieval / citations — still open):** Re-run corpus QA / local RAG harness after prod re-index if needed; optional **metadata backfill** `summaries=false` on legacy chunk rows; **rerank** still deferred; confirm **local power company / VD** queries under new retrieval in real traffic.

---

### 14. Sub-Workflow System Architecture

**Status:** 📋 To Do

**Goal:**
Expand the current workflow architecture to support sub-workflows that are dynamically triggered based on user requests. The LLM decides which sub-workflow to execute.

**Product direction (office copilot):**
- Target experience: a worker-facing assistant (similar in spirit to coding assistants) for office work: mail, Teams, SharePoint, ERP (orient on **Salesforce** for now), documents/contracts.
- Example: user asks in Teams to **create a customer-specific contract** → orchestrator gathers context (example contracts, ERP customer data, relevant email thread), generates a file, returns it to the worker, optionally prepares an **email draft** (not send) for review.
- **Tooling preference:** expose integrations as **HTTP APIs or controlled CLIs** (MCP optional elsewhere); each tool has **limited, configurable scope** (e.g. read-only mail, draft-only mail, no send) — enforce in **code + permission scopes**, with admin/user policy configuration.

**Architecture Requirements:**
- Modular sub-workflow design for easy addition of new workflows
- LLM-based routing to determine appropriate sub-workflow
- Clear interface/contract for sub-workflow implementation
- Graceful fallback to main RAG workflow when no sub-workflow matches
- **Server-side tool policy** (allowlist per operation: search/read/draft/send) — default conservative (e.g. no send in v1)

**Initial Sub-Workflows:**

**14a. Testing Workflow**
- Purpose: TBD (details to be provided)
- Implementation: N8N workflow prototype first
- Integration with main bot flow

**14b. Document Update Workflow (Admin Only)**
- Purpose: Allow admin users to update documents in the vector database
- Use case: Fix errors in customer documentation without full re-indexing
- Access control: Admin role verification required
- Options to investigate:
  - Create new document version and re-index specific chunks
  - Replace/update chunks for specific document
  - Document ID-based targeting
- Audit logging for all document modifications

**14c. Microsoft 365 integrations (Outlook / SharePoint / Teams via Graph)**

**Current codebase (gap):** The Azure-hosted bot uses **client credentials** only for **Bot Framework** (`https://api.botframework.com/.default`). There is **no** Microsoft Graph app permission in Terraform ([`infrastructure/bot.tf`](../infrastructure/bot.tf)) and **no** Graph client in `teams-bot/`. **Outlook read/search/draft is not possible until this is added.**

**Recommended approach (worker’s mailbox):**
- **Teams SSO → On-Behalf-Of (OBO) → Microsoft Graph** with **delegated** scopes (start with `Mail.Read`; add `Mail.ReadWrite` only if drafts are required). Implement narrow LangGraph tools: mail search/read, create draft — **do not** call send APIs in v1.
- Add Graph `required_resource_access` (or document portal steps), **Azure Bot OAuth connection**, OBO token handling in Azure Functions, short-lived tokens passed into tools (no token logging).

**Same pattern extends to:** SharePoint/OneDrive (files/sites scopes), additional Teams scenarios beyond chat reply (channel APIs need extra scopes). **Replying in the current chat** stays **Bot Framework** (already implemented).

**Limits / not automatic:**
- **External customer mailboxes** outside the tenant are not available via Graph; delegated access is **what the signed-in worker can see**. Broad **application** mail permissions are tenant-wide and high risk — only if explicitly approved.
- **Salesforce** is a **separate** OAuth/API integration (not Graph).

**Implementation checklist (high level):**
- [ ] Decide: extend bot app registration vs separate “integration” app for Graph
- [ ] Azure AD: delegated Graph permissions + consent; OAuth connection on Azure Bot; redirect URIs as per Teams SSO docs
- [ ] Functions: acquire Graph token (OBO), Graph HTTP tools, policy layer per tool
- [ ] Optional: correlate with `aadObjectId` from activity when present (not a substitute for user token)

**Future Sub-Workflows:**
- Architecture should support easy addition of new sub-workflows
- Consider plugin-like architecture or workflow registry pattern
- **Salesforce (ERP)** sub-workflow: separate connector and credentials

**Technical Considerations:**
- How to identify admin users in Teams context
- Sub-workflow state management
- Error handling and rollback for failed updates
- Integration with existing LangGraph architecture
- Token storage/TTL for OAuth (per user/conversation) and Graph throttling

**Planning note:** Detailed Outlook/Graph analysis lives in the Cursor plan *Outlook access architecture* (`.cursor/plans/`); keep this task as the actionable tracker in-repo.

**Use-case prompts and external reference review (meeting 2026-04):**
- Add **specified prompts per use case** as sub-workflows are introduced — e.g. **email** (drafting, summarizing threads, tone), aligned with server-side tool policy above.
- **Review** (for ideas and terminology only; open-source / unofficial analyses — do not treat as product requirements):
  - [claurst](https://github.com/Kuberwastaken/claurst) — open-source multi-provider terminal coding agent in Rust; agent loop, tools, plugins.
  - [Sabrina Ramonov — analysis of Claude Code source leak](https://www.sabrina.dev/p/claude-code-source-leak-analysis) — agent architecture, compaction, safety/tooling themes relevant to long-running assistants.
  - [Claude Code Unpacked](https://ccunpacked.dev/) — unofficial map of agent loop, tools, and commands (validate against our own design).

---

### 15. Website Development

**Status:** 📋 To Do

**Goal:**
Create and maintain a website for RAGStone, adding the website development to this repository.

**Scope:**
- Product landing page
- Feature documentation
- Setup guides and tutorials
- Pricing/plans information (if applicable)
- Contact and support information

**Technical Decisions Needed:**
- Framework selection (Next.js, Astro, etc.)
- Hosting (Azure Static Web Apps, Vercel, etc.)
- Repository structure (monorepo with website folder)
- CI/CD pipeline for website deployment

---

### 19. Customer feedback process (Teams)

**Status:** 📋 To Do

**Goal:** Build a **feedback and error-reporting** path for customers who interact with the AI via **Microsoft Teams**, so issues are stored **separately** from normal chat, classified, and routed to the right follow-up (developers vs admins vs automated handling).

**Requirements:**
- **Dedicated Teams affordance** — e.g. a **slash command** or structured card — for “report error / feedback” (distinct from free-form chat).
- **Separate storage** from general conversation history for triage, metrics, and fix tracking.
- **Classification** into three types (each with different handling):

| Type | Examples | Handling |
|------|----------|----------|
| **System errors** | No reply; missing access; explicit error surfaced to user | Notify **developers** with **service logs for the relevant time window** + **conversation transcript**. May also be **raised automatically** by health checks or caught exceptions. |
| **Quality / behavior** | Slow responses; wrong answer when **documentation is correct**; tone or behavior issues | Notify **developers** with **transcript** + **user description**. Typically **user-initiated**. |
| **Data / corpus quality** | Wrong answer because **source documentation is wrong or outdated** | **Guided workflow** with user input (see below). |

**Data-quality workflow (corpus wrong):**
1. User signals that information is wrong.
2. Bot/AI collects structured follow-up: **which document or topic**, **what is wrong**, **what should be correct**.
3. **Bot admin:** locate corpus record, confirm with user, **replace** outdated material (remove old chunks/records, ingest corrected content), write **audit metadata** (who corrected, when).
4. **Non-admin user:** collect the same structured info and **notify bot admins** for manual correction (and optional ticket).

**Implementation notes:** Align with observability (e.g. `RAG_TURN_AUDIT`, Application Insights) for system errors; define Teams UX and backend persistence (tables or existing stores).

---

### 20. Knowledge base architecture — research and future restructure

**Status:** 📋 To Do  
**Priority:** Medium — large scope; **defer implementation** until higher-urgency items land.

**Goal:** Plan a longer-term **restructure** of organizational knowledge (not only flat chunk retrieval): navigation, linking, and maintainability at scale.

**Research themes (from meeting):**
- **Confluence-like UX** — hierarchy, browse/search, page ownership.
- **Knowledge graphs** — entities, relations, and when they help vs hurt.
- **Links and cross-citations** — between pages, policies, and annexes.

**Deliverable (phase 1):** Design note comparing options, cost, and fit with `pinecone-pipeline` + bot; **no build commitment** until reviewed.

---

### 21. PDF and DOCX extraction — completeness and structure

**Status:** 📋 To Do

**Goal:** **Review** ingestion paths that read **PDF** and **DOCX** so extracted text is **complete** and **structure** (headings, lists, tables where supported) is preserved well enough for chunking, retrieval, and citations.

**Scope:** Audit pipeline code in `pinecone-pipeline/` (and shared helpers); document gaps (e.g. complex tables, scans, footnotes); propose library or preprocessing changes as needed.

---

### 24. Folder- and file-aware retrieval (client: `opis folderów.docx`)

**Status:** ✅ Phase A completed — prod **2026-04-10** (`2449fe0`); extended in Wave 3 **`c639099`**. **Phase B** (narrow→broad loop) deferred

**Goal:** Use a **human-authored description of folders and files** (client-provided document) so the **routing / optimizer** agent can **narrow search** before falling back to full-corpus retrieval.

**Implemented (2026-04):** `pinecone-pipeline/source_data/opis folderów.docx` (copy of repo-root file); optional `folder_map_prompt.md` + `folder_map_loader.py` for optimizer appendix; `RAGStrategy.corpus_path_prefix` + `merge_corpus_path_prefix` in retrieval; see [folder-map-prompt.md](../.cursor/skills/knowledge-base-curator/folder-map-prompt.md).

**Approach (meeting notes — refine during design):**
- Incorporate content from **`opis folderów.docx`** into the **prompt of the agent that plans retrieval** — **not** necessarily as indexed vectors; treat as **authoritative map** for scope decisions.
- Prefer existing **metadata** (`corpusTopic`, `corpusPathPrefix`, path segments) when present.
- **Preferred flow:** **fast, scoped retrieval** using inferred folder/file → if the answer is not good enough, **broaden** to wider search.
- **Open point:** exact rule for when to escalate (optimizer judgment, relevance score, explicit user follow-up). **Phase B (narrow→broad loop):** deferred until multi-step graph design is finalized.

**Prerequisite:** Confirm rights to embed the document text in prompts; keep in sync if the folder layout changes.

---

## Completed Tasks

### 32. TTFT — real token streaming on the Teams answer path

**Priority:** High

**Status:** ✅ Completed — shipped dev + prod (`b279fc3`, prod deploy train from **2026-05-08** `1ce0469`)

**Goal:** Users see the first answer tokens **before** the full LLM completion; final message still carries grounded citations.

**Implementation:** `astream_teams_entry_tokens` + `precompute_streaming_citation_map` + monotonic `streaming_safe_remapped_text`; 22 tests in `tests/test_streaming_citation_remap.py`. Teams **2-minute** streaming limit tracked under task **26**.

---

### 31. Conversation context cache + history TTL + hourly purge

**Priority:** High

**Status:** ✅ Completed — shipped dev + prod (`af8654c`, `f470d17`; prod deploy train from **2026-05-08**)

**Goal:** Skip or narrow Pinecone when the optimizer sets `reuse_previous_context`; persist last retrieval per user; history limit **50**; hourly purge.

**Implementation:** `conversation_context` table, cache-aware optimizer, audit fields for reuse KQL, `purge_stale_storage` timer. Env: `HISTORY_MESSAGE_LIMIT`, `HISTORY_TTL_HOURS`, `CONTEXT_CACHE_TTL_HOURS`.

---

### 30. Conversation-aware RAG prompt

**Priority:** High

**Status:** ✅ Completed — shipped dev + prod (`f470d17`; prod deploy train from **2026-05-08**)

**Goal:** Pass recent chat history into the **answer** LLM so follow-ups reuse prior assistant context.

**Implementation:** `MessagesPlaceholder("history")` in `nodes.py` (last 12 prior messages); optimizer history for routing only (`optimized_query` current-turn-only).

---

### 23. Citations: only sources used in the answer (ASAP)

**Priority:** High

**Status:** ✅ Completed — dev verified + prod **2026-04-10** (`2449fe0` / deploy log)

**Goal:** Attach citations only to sources that ground the final answer.

**Implementation:** `CITATIONS_USED` line; `filter_sources_by_indices`, `merge_adjacent_same_document_chunks` in `citations.py` / `nodes.py`.

---

### 22. Intermediate status messages during long vector retrieval (ASAP)

**Priority:** High

**Status:** ✅ Completed — dev verified + prod **2026-04-10** (`2449fe0` / deploy log)

**Goal:** Intermediate Teams status messages during optimize / retrieve phases.

**Implementation:** `status_copy.py`; phase callbacks in `function_app` and `RAGNodes.retrieve` (`vector_search`, `scoped_fallback`, `neighbor_expansion`, `context_ready`).

---

### 6. Multi-Organization Deployment (Single-Tenant per Customer)

**Status:** ✅ Completed

**Context:**
Multi-tenant bot creation was deprecated by Microsoft in July 2025. We use a single-tenant deployment model where each customer organization gets their own isolated bot instance in their Azure tenant.

**Implemented:**

**Terraform Infrastructure:**
- ✅ Added `tenant_id` and `subscription_id` variables to `variables.tf`
- ✅ Updated `providers.tf` to use explicit tenant/subscription from variables
- ✅ Created `infrastructure/environments/dev.tfvars` and `prod.tfvars`
- ✅ Fixed `functions.tf` to use `SingleTenant` with `MICROSOFT_APP_TENANT_ID`
- ✅ All sensitive config (tenant/subscription IDs, API keys) loaded from `.env`

**Deployment Scripts with Branch Protection:**
- ✅ Created `scripts/terraform.sh` - wrapper with environment selection, `.env` loading, branch check
- ✅ Updated `scripts/deploy-fast.sh` - accepts environment param, branch check for prod
- ✅ Updated `scripts/deploy-full.sh` - accepts environment param, branch check for prod
- ✅ Production deployments only allowed from `release` branch

**Teams App Package Generation:**
- ✅ Updated `build-package.ps1` to accept Bot ID and Environment parameters
- ✅ Generates environment-specific package (e.g., `northwind-ai-prod.zip`)

**Documentation:**
- ✅ Updated `infrastructure/README.md` with multi-tenant deployment guide
- ✅ Updated `scripts/README.md` with new script usage
- ✅ Updated `docs/customer-support/CUSTOMER-SETUP-EN.md` and `docs/customer-support/CUSTOMER-SETUP-PL.md` for single-tenant model
- ✅ Updated `.env.example` with Azure tenant/subscription variables

**Tested:**
- ✅ Dev deployment with `./scripts/terraform.sh dev apply`
- ✅ Bot health check passed

**For Production Deployment (Northwind Residences):**
1. Customer provides Tenant ID and Subscription ID
2. Customer grants Contributor + Application Administrator access
3. Create `release` branch, update `.env` with customer values
4. Run `./scripts/terraform.sh prod apply`
5. Deploy bot code with `./scripts/deploy-fast.sh prod`
6. Build Teams package with customer's bot ID

**Pinecone:**
- Per-customer namespaces in Pinecone
- Namespace naming convention (e.g., `northwind-prod`)

**Known Issue — Terraform Workspace Naming:**
- Dev environment uses the `default` workspace, but deploy scripts (`deploy-fast.sh`, `deploy-full.sh`) expect a workspace named `dev`. Align by either renaming the workspace or updating the scripts.

---

### 10. UX Improvements & Token Streaming Optimization

**Status:** ✅ Completed

**Problems:**
1. Streaming latency - users waited 3-5s for first text to appear (full response generated before streaming)
2. Generic prompts - not personalized for Northwind Residences brand
3. Error messages exposed technical details to users

**Solutions Implemented:**

**Token-by-Token Streaming:**
- Added `astream_respond_with_rag()` and `astream_respond_direct()` to stream tokens from LLM
- Teams orchestration uses `rag/teams_entry.astream_teams_entry`; inner RAG uses `build_teams_pipeline` / `complete_response_from_work` / `run_teams_turn_nonstream` (harness)
- First tokens now visible within ~500ms of LLM start (vs 3-5s before)
- Chunks sent after 50 characters or 1-second rate limit

**Improved Polish Prompts:**
- `SYSTEM_PROMPT` - Friendlier Northwind Residences brand personality
- `WELCOME_MESSAGE` - Warmer greeting with example questions
- `DIRECT_RESPONSE_PROMPT` - Natural conversational tone

**Error Handling:**
- Added `ERROR_MESSAGE` constant with user-friendly Polish message
- Technical errors logged via `logger.exception()` for debugging
- Users see generic message: "Przepraszam, wystąpił tymczasowy problem..."

**Key Files:**
- `teams-bot/rag/prompts.py` - Updated prompts + ERROR_MESSAGE
- `teams-bot/rag/nodes.py` - Token streaming methods
- `teams-bot/rag/graph.py` - `build_teams_pipeline`, `run_teams_turn_nonstream`, `StreamingResult`
- `teams-bot/function_app.py` - Real-time token consumption

**Deployment:**
- Deployed and tested 2026-01-24

---

### 3. Make RAG Context Optional + 7. Conversation History (LangGraph Upgrade)

**Status:** ✅ Completed

**Problem:**
1. Every message triggered Pinecone search, even greetings like "Cześć"
2. No conversation memory - each message was independent

**Solution Implemented:**
Migrated from simple LangChain RAG to LangGraph-based architecture with:

**Conditional RAG Routing:**
- LLM-based RAG optimizer decides IF and HOW to search documents
- Skips RAG for greetings, confirmations, meta-questions, follow-ups
- Dynamic **`num_documents` (10–20)** and optional **summary-first** tier (`retrieval_tier`); legacy **2–6** superseded
- Query rewriting for better vector search results

**Conversation Memory:**
- Azure Table Storage for persistent per-user chat history
- Uses existing Storage Account (no new infrastructure)
- History survives bot restarts and redeployments
- Last **50** messages loaded for context by default (`HISTORY_MESSAGE_LIMIT`; previously 10 until task **31**)

**Key Files:**
- `teams-bot/rag/graph.py` - LangGraph StateGraph workflow
- `teams-bot/rag/optimizer.py` - LLM-based RAG strategy
- `teams-bot/rag/nodes.py` - Node functions (optimize, retrieve, respond)
- `teams-bot/rag/memory.py` - Azure Table Storage conversation store
- `teams-bot/function_app.py` - Updated to use LangGraph

**Architecture:**
```
User Message → Load History → LLM: Plan RAG Strategy
    ↓
Needs RAG? ─Yes→ Retrieve k Documents → Generate Response
    │
    └──No→ Direct LLM Response → Save to History → Send Response
```

**Deployment:**
- Deployed and tested 2026-01-24
- Two deployment scripts: `deploy-fast.sh` (~30s) and `deploy-full.sh` (~2min)
- Documentation updated: `deployment-ops` skill, `docker-images.md`, `scripts/README.md`

---

### 1. Migrate Teams Bot from N8n to Azure Functions

**Status:** ✅ Completed

**Problem:**
The original N8n cloud-based workflow had a 15-second webhook timeout limit, causing message delivery failures for longer AI responses.

**Solution Implemented:**
Migrated to Azure Functions with a custom Python backend that:
- Responds immediately to webhooks (prevents timeout)
- Uses LangChain for RAG pipeline with Pinecone vector store
- Integrates with OpenAI for embeddings and chat completion
- Returns answers with source citations

**Infrastructure (Terraform-managed):**
- Azure Functions (Consumption plan)
- Azure Bot Service (SingleTenant)
- Azure Key Vault for secrets
- Azure Storage Account

**Key Files:**
- `teams-bot/function_app.py` - Main webhook handler
- `teams-bot/rag/graph.py` - LangGraph RAG (Pinecone + optimizer)
- `teams-bot/bot/streaming.py` - Teams Streaming API (ready for future use)
- `infrastructure/` - Terraform configuration

---

### 2. Enable Teams Streaming API

**Status:** ✅ Completed

**Problem:**
Bot sent a single complete message after RAG processing, with no feedback during the wait.

**Solution Implemented:**
Enabled progressive message delivery using Teams Streaming API:
- Informative updates during processing ("Przeszukuję dokumenty...", "Generuję odpowiedź...")
- Real-time text streaming with 1.5s buffered token delivery
- Proper handling of API requirements (streamId, non-empty chunks, required fields)

**Key Changes:**
- `teams-bot/function_app.py` - Integrated `TeamsStreamer` with buffered token streaming
- `teams-bot/bot/streaming.py` - Fixed API compliance issues
- `scripts/deploy-fast.sh` - Added fast deployment script with `--no-build`
- `Dockerfile.dev` - Updated to Python 3.11 for Azure compatibility

---

### 4. Migrate to uv Package Manager

**Status:** ✅ Completed (partial)

**Goal:**
Replace pip with uv for faster, more reliable Python dependency management.

**Changes Implemented:**
- `pinecone-pipeline/` uses uv with `pyproject.toml`
- `Dockerfile.dev` includes uv for local development
- Dev container has uv available

**Limitation Discovered:**
Azure Functions deployment requires `requirements.txt` - there's no native uv support on the Azure platform. Therefore `teams-bot/` continues to use pip with `requirements.txt`.

**Result:** Hybrid approach - uv for local tools (pinecone-pipeline), pip for Azure-deployed code (teams-bot)
