# Northwind Assistant Teams Bot

Azure Functions (Python) Teams bot: **inner** RAG (optimizer → retrieve → answer), Teams **Streaming API** in 1:1 chats, and optional **Azure Table Storage** memory (with a short TTL in-process history cache).

**Extended docs:** [`docs/README.md`](docs/README.md) (user-facing PL summary, investigations, Wave 3 notes).

## Features

- **RAG path** — Structured optimizer (`OPENAI_OPTIMIZER_MODEL`), Pinecone retrieval (scopes / tiers / optional summary-first), answer generation (`OPENAI_MODEL`) with Polish prompts.
- **Streaming UX** — Informative status lines (`bot/status_copy.py`) during history load, planning, retrieval, and before the answer LLM; then cumulative chunks of the authoritative answer.
- **Citations** — `Źródła` block from retrieved chunks; SharePoint-style links when metadata has `sharepointUrl` or the Function App has a library base URL set (Terraform: `sharepoint_library_base_url` → `SHAREPOINT_LIBRARY_BASE_URL`). **How it works / where to change:** [`../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md`](../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md).
- **Memory** — Per-user history in Azure Table Storage when `AzureWebJobsStorage` / `AZURE_STORAGE_CONNECTION_STRING` is configured.
- **Observability** — `RAG_TURN_AUDIT` JSON per turn; `TEAMS_TURN_LATENCY` per-step timings (`trace_id` = Functions `invocation_id`).

## Architecture

```
Teams (1:1)
    → Azure Bot Service
    → Azure Functions  teams_webhook
        → process_message (turn_latency_scope)
            → TeamsStreamer: informative + stream + final
            → astream_teams_entry (rag/teams_entry.py)
                → build_teams_pipeline + complete_response_from_work
                    → optimize → retrieve? → respond_with_rag | respond_direct
            → stream StreamingResult.full_response to Teams
            → log_rag_turn_audit
```

Inner nodes match the compiled LangGraph in `rag/graph.py` (`optimize` → `retrieve` | `respond_direct` → `respond_with_rag`); the Teams tool path runs the same node functions sequentially for callbacks and latency.

## Project structure

```
teams-bot/
├── function_app.py          # HTTP triggers: /api/messages, /api/health
├── config.py                # Env → AppConfig (bot, OpenAI, Pinecone, storage)
├── host.json
├── requirements.txt
├── local.settings.json.example
├── bot/
│   ├── activity_handler.py  # Parse Teams activities
│   ├── streaming.py              # Bot Framework streaming + rate limit
│   ├── bot_framework_token.py    # Optional cold-start token pre-fetch
│   ├── status_copy.py            # Polish status strings
│   └── turn_latency.py           # TEAMS_TURN_LATENCY context + emit helper
├── web/                     # OpenAI-compatible facade for LibreChat (Phase 1)
│   ├── app.py               # FastAPI: GET /v1/models, POST /v1/chat/completions (SSE)
│   ├── openai_compat.py     # Auth, message mapping, chunk helpers
│   └── web_entry.py         # Status → reasoning_content; citations; audit channel=web
├── rag/
│   ├── graph.py             # RAGGraph, Teams pipeline, LangGraph compile
│   ├── teams_entry.py       # Teams turn: pipeline + StreamingResult
│   ├── nodes.py             # optimize, retrieve, respond_* , retrieval phases
│   ├── optimizer.py         # RAGStrategy structured output
│   ├── prompts.py           # Answer / direct system prompts
│   ├── citations.py         # Citation block + SharePoint URL helpers
│   ├── request_audit.py     # RAG_TURN_AUDIT logging
│   ├── memory.py            # Table storage conversation memory
│   ├── retrieval_filter.py  # Pinecone metadata filters / scopes
│   └── …                    # pinecone_ids, folder_map_loader, etc.
└── scripts/                 # e.g. clear_conversation_memory.py, run_local_rag_tests.py
```

## LibreChat web adapter (local)

FastAPI sidecar (not Functions) for reliable SSE. Same OpenAI + Pinecone env as the bot; set `RAG_WEB_API_KEY`.

```bash
cd teams-bot
pip install -r requirements.txt
# export OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME, PINECONE_NAMESPACE, RAG_WEB_API_KEY
python -m web.app
# → http://127.0.0.1:8081/v1/models
# → http://127.0.0.1:8081/v1/chat/completions  (SSE when stream=true)
```

Point LibreChat at `http://host.docker.internal:8081/v1` — see [`../librechat/README.md`](../librechat/README.md).

**Hosting note:** Azure Functions can expose HTTP, but long-lived SSE is awkward on the Python worker; the adapter is a small ASGI app that can later run on Container Apps beside LibreChat. Teams continues on Functions unchanged.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure local settings

```bash
cp local.settings.json.example local.settings.json
```

Edit values: Bot Framework IDs, `MICROSOFT_APP_TENANT_ID`, OpenAI, Pinecone, optional `AzureWebJobsStorage` (Azurite or real storage for memory).

### 3. Run locally

```bash
func start
```

Endpoints: `http://localhost:7071/api/messages`, `http://localhost:7071/api/health`.

### 4. Bot Framework Emulator (optional)

1. [Bot Framework Emulator](https://github.com/microsoft/BotFramework-Emulator)
2. Endpoint `http://localhost:7071/api/messages`
3. For local-only testing, App ID / password may be empty depending on your security settings; production uses registered app secrets.

## Deployment

Terraform creates the Function App shell; bot code is published separately.

- **Deploy:** [`.cursor/skills/deployment-ops/SKILL.md`](../.cursor/skills/deployment-ops/SKILL.md) (Terraform vs `deploy-fast` / `deploy-full`, Docker helpers, health check).
- **Typical (dev):** on branch `main`, from repo root: `./scripts/deploy.sh dev` (or `scripts\deploy.cmd dev` on Windows — see [`../scripts/README.md`](../scripts/README.md)).

Raw example (host has Azure Functions Core Tools + auth):

```bash
cd ../infrastructure && terraform output -raw function_app_name
cd ../teams-bot && func azure functionapp publish <name> --python
```

Pinecone index/namespace on the app are often synced from Terraform tfvars during deploy scripts; prefer the documented script flow so settings match the environment.

**SharePoint citation URLs** (metadata + base URL, Terraform tfvars, sync script): [`../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md`](../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md).

## Streaming flow (1:1)

1. Webhook returns **200** quickly; processing continues in the same invocation.
2. **Informative:** `Analizuję pytanie…` (`analyzing_question()`), then throttled updates for history load, optimizer start, optimize outcome, retrieval phases, retrieve counts, and answer composition (`status_copy.py` + `after_*` callbacks).
3. After **`StreamingResult`**: cumulative **streaming** chunks of `full_response`, then **final** message (body + optional **Źródła** from `format_citations`).
4. **Group chats:** streaming/informatives are skipped; behavior falls back to non-streaming paths where implemented.

## Environment variables

| Variable | Description |
|----------|-------------|
| `MICROSOFT_APP_ID` | Bot App (client) ID |
| `MICROSOFT_APP_PASSWORD` | Client secret |
| `MICROSOFT_APP_TYPE` | Default `SingleTenant` |
| `MICROSOFT_APP_TENANT_ID` | Azure AD tenant for token endpoint |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Chat model for **inner** answers: `respond_with_rag`, `respond_direct` |
| `OPENAI_OPTIMIZER_MODEL` | RAG optimizer structured output (default `gpt-5-nano`) |
| `HISTORY_MESSAGE_LIMIT` | Max Table Storage messages loaded per turn (default `10`; `-1` = all) |
| `HISTORY_CACHE_TTL_SECONDS` | In-process history cache TTL (default `30`; `0` disables) |
| `HISTORY_CACHE_MAX_USERS` | Max users in the in-process history cache (default `256`) |
| `MAX_RAG_CONTEXT_CHARS` | Cap on formatted RAG context chars (default `48000`); chunks ranked by Pinecone score before cap |
| `RAGSTONE_DISABLE_PREWARM` | Set to `1` to skip cold-start graph + token pre-warm thread |
| `OPENAI_EMBEDDING_MODEL` | Embeddings (must match Pinecone index dimension) |
| `PINECONE_API_KEY` | Pinecone API key |
| `PINECONE_INDEX_NAME` | Index name (preferred); `PINECONE_INDEX` still accepted |
| `PINECONE_NAMESPACE` | Namespace (e.g. `v3`) |
| `SUMMARY_RETRIEVAL_ENABLED` | `0` (default): force chunk-only retrieval in code; `1`: allow summary-first path when summary vectors exist |
| `RAG_NEIGHBOR_EXPANSION_ENABLED` | `0` (default): no ±1 chunk expansion; `1`: extra Pinecone fetches for neighbors |
| `RAG_ANCHOR_RETRIEVAL_ENABLED` | `1` (default): run a **second** Pinecone semantic query in parallel, restricted to fixed handbook `sourceRelativePath` values (default: **Instrukcja dla nowego pracownika 2025.pdf** only), and prepend hits before scoped retrieval (deduped). `0` disables. |
| `RAG_HANDBOOK_DIRECT_ENABLED` | `0` (default): always full Pinecone RAG for Instrukcja/CRM/tenant questions. `1` = legacy handbook direct path (inlined JSON, no search). Instrukcja bias: `RAG_ANCHOR_RETRIEVAL_ENABLED`. |
| `RAG_ANCHOR_CHUNK_K` | Top‑`k` for that anchor query (default `6`, max `24`) |
| `RAG_ANCHOR_SOURCE_RELATIVE_PATHS` | Optional comma‑separated paths (under `source_data/`) overriding the built‑in defaults |
| `RAG_INLINE_SAME_DOC_CITATION_COLLAPSE_ENABLED` | `1` (default): collapse comma‑separated `[Źródło a], [Źródło b], …` to one tag when all map to the same `sourceRelativePath` / `fileName`. `0` disables. |
| `SHAREPOINT_LIBRARY_BASE_URL` | Base URL of the SharePoint folder that mirrors `source_data/` (Terraform sets `…/AI/dev` vs `…/AI/prod` per environment) so citations resolve when chunks only have `sourceRelativePath`. If unset, `SHAREPOINT_BASE_URL` (same name as the Pinecone indexer) is used. |
| `USER_PREFERENCES_MAX_CHARS` | Max length for `/style` preference text stored in Table `userpreferences` (default 2000) |
| `AzureWebJobsStorage` / `AZURE_STORAGE_CONNECTION_STRING` | Functions state + **conversation memory** table when non-empty |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Azure: traces + **`RAG_TURN_AUDIT`** / **`TEAMS_TURN_LATENCY`** JSON in `traces` |

## Observability

| Log prefix | Purpose |
|------------|---------|
| `RAG_TURN_AUDIT` | One JSON object per completed turn: user message, assistant text, `needs_rag`, `optimized_query`, retrieval fields, `azure_invocation_id`, compact `retrieved_documents`. Implementation: [`rag/request_audit.py`](rag/request_audit.py). |
| `TEAMS_TURN_LATENCY` | Per-step `elapsed_ms` (from turn start), optional `segment_ms`, Bot Framework `http_ms` on posts. `trace_id` matches `azure_invocation_id` in the audit row. |

**Query in Azure:** Application Insights → Logs, e.g. `traces | where message startswith "RAG_TURN_AUDIT" | order by timestamp desc`.

**Logs / KQL:** [`bot-quality-evaluation` skill](../.cursor/skills/bot-quality-evaluation/SKILL.md) + [`../scripts/kql/README.md`](../scripts/kql/README.md).

## Troubleshooting

### "Token acquisition failed"

- Check `MICROSOFT_APP_ID`, `MICROSOFT_APP_PASSWORD`, and `MICROSOFT_APP_TENANT_ID`.
- Registration must match **`MICROSOFT_APP_TYPE`** (repo defaults to **SingleTenant**).

### Streaming not working in group chat

Expected: Teams streaming API is for **1:1**; group/channel handling skips informatives and streaming sends per [`bot/streaming.py`](bot/streaming.py).

### Rate limits

- Streamer enforces ~**1 request/second** between streaming posts.
- Separate limits may apply for OpenAI and Pinecone; reduce `OPENAI_MODEL` load or retrieval `k` if needed.

### No audit/latency rows

Confirm `APPLICATIONINSIGHTS_CONNECTION_STRING` on the Function App and that the deployed build includes `log_rag_turn_audit` / `turn_latency_scope`.
