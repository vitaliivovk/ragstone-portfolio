# Conversation mining → process discovery (Phase 5)

Scaffolding for mining recurring office tasks from web chat, then promoting them into versioned process definitions (Phase 4 [`process-engine/`](../../process-engine/)). **No live Azure/KQL/Mongo calls in v0** — offline fixtures + heuristics only.

**Frontend gate (same phase):** when document-IDE UX is required, evaluate exit from LibreChat using [`FRONTEND-EXIT-CRITERIA.md`](FRONTEND-EXIT-CRITERIA.md). Mining and the frontend decision are independent deliverables; both land in Phase 5 of the Office IDE roadmap.

## Inputs

| Source | What it provides | Join key |
|--------|------------------|----------|
| **LibreChat Mongo** | Full conversation transcripts, titles, timestamps, Entra user id | LibreChat `conversationId` |
| **`RAG_TURN_AUDIT`** (App Insights / Log Analytics) | Per-turn structured RAG forensics: `optimized_query`, `retrieval_scope`, `answer_topic`, `response_path`, compact `retrieved_documents`, `context_chunk_ids`, `channel` | `conversation_id` (+ `channel=web` for LibreChat) |

Web adapter already emits audits with `channel: "web"` and Entra oid in `teams_user_id` (see `teams-bot/rag/request_audit.py`). Filter mining to `channel == "web"` so Teams history does not pollute web process discovery (separate id spaces).

**Export shape (offline):** JSON array of audit payloads (fixture or KQL export later). Optional companion Mongo export is out of scope for the stub — clustering v0 uses audit fields only.

## Clustering approach (v0)

Goal: surface **recurring task patterns**, not one-off Q&A.

1. **Filter** — keep turns with `response_path` in `{rag, clarify}` (drop pure `smalltalk`); require non-empty `conversation_id`.
2. **Feature key** — coarse signature:
   - `answer_topic` (composer topic, or `"none"`)
   - `retrieval_scope`
   - top-N corpus path prefixes from `retrieved_documents[].sourceRelativePath` (first path segment / folder slug)
3. **Cluster** — group turns that share the same feature key across conversations (or within a conversation for multi-turn rituals).
4. **Score** — cluster size (≥ N distinct `conversation_id`s) and optional repeat rate per user. v0 stub: size ≥ 2 → candidate.
5. **Sketch** — emit a **candidate process** dict compatible with `process_engine.schema.ProcessDefinition` fields (`id`, `version`, `title`, `inputs`, `steps`, `output_template`), marked `status: "candidate"` / `never_send: true` for email drafts.

Later (not in stub): embedding similarity on `user_message` / `optimized_query`, session-level sequences (clarify → rag → draft), MCP tool call audits from plugins.

## Promote-to-process flow

```text
audits (+ optional Mongo) → clusters → candidate sketches
                                      ↓ human review
                           process-engine catalog (versioned JSON)
                                      ↓
                           MCP list_processes / run_process (curated agents)
```

1. Operator (or future admin UI) reviews candidate sketches — rename, add inputs, drop noisy steps.
2. Validate with `process_engine.schema.validate_process_dict`.
3. Write into the process-engine catalog (new `id@version`); bump version on edits.
4. Expose via curated LibreChat agent / MCP; **never auto-promote** without human approval.
5. First hand-authored process remains `standard_client_reply` (Phase 4); mining feeds the backlog of the next definitions.

Stub entry point: `conversation_mining.sketch.sketches_from_audits(...)` — see [`conversation-mining/`](../../conversation-mining/).

## Privacy and retention

| Constraint | Guidance |
|------------|----------|
| **Purpose limitation** | Mining is for process discovery and quality, not employee surveillance. Aggregate patterns; do not build per-user performance dashboards from raw chat in v1. |
| **PII in audits** | `user_message` / `assistant_response` may contain client PII. Prefer clustering on `answer_topic`, scopes, and path prefixes; redact or hash message bodies in long-lived mining stores. |
| **Access** | App Insights + Mongo access limited to operators with existing prod forensics rights (same bar as task **36**). |
| **Retention** | Align with customer DPA / App Insights retention; mining exports are ephemeral working sets — delete after promotion or after an agreed window (e.g. 30–90 days). |
| **Tenant isolation** | Cluster and store per `tenant_id` / deployment; never mix customer Mongo or audit exports. |
| **Channel** | Default to `channel=web`; Teams audits only if product explicitly expands mining later. |

## Related

- Process schema / runner: [`process-engine/`](../../process-engine/)
- Frontend exit gate: [`FRONTEND-EXIT-CRITERIA.md`](FRONTEND-EXIT-CRITERIA.md)
- Audit emitter: [`teams-bot/rag/request_audit.py`](../../teams-bot/rag/request_audit.py)
- Task tracking: [`docs/TASKS.md`](../TASKS.md) #39
