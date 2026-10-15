# Reading Azure logs (KQL + Docker)

Use the **dev Docker image** so you do not need Azure CLI on the host. Logs live in **Application Insights** (table `traces` for the default API) and in the linked **Log Analytics workspace** (tables like `AppTraces`).

**Canonical entrypoint:** `scripts/run_kql.sh` — pass a **`.kql` file**, **`-q '...'`** (inline Kusto), or **stdin** (`-` or a pipe).

---

## Prerequisites

1. **Repository root** (folder that contains `docker-compose.dev.yml`).
2. **Docker Desktop** running.
3. **One-time login** inside the dev container (Azure CLI config is stored in the `azure-config` volume):

   ```bash
   docker compose -f docker-compose.dev.yml run --rm dev bash -lc "az login && az account show"
   ```

4. **Subscription** — set `DEV_AZURE_SUBSCRIPTION_ID` / `DEV_AZURE_TENANT_ID` (or legacy `AZURE_*` for dev) in `.env` so deploy and `az` commands target the right tenant. Deploy scripts already use this; `run_kql.sh` relies on the same `az` session.

---

## Run queries (`run_kql.sh`)

Always use **`-T`** (no TTY allocate) when piping or batching:

```bash
docker compose -f docker-compose.dev.yml run --rm -T dev bash /workspace/scripts/run_kql.sh scripts/kql/last_rag_turn.kql
```

### Input modes

- **`.kql` file:** `… run_kql.sh scripts/kql/rent_payment_audit.kql`
- **Inline:** `… run_kql.sh -q 'traces | take 3'` (single quotes on Linux/bash; see Windows below)
- **Stdin:** `cat scripts/kql/foo.kql | docker compose … run --rm -i -T dev bash /workspace/scripts/run_kql.sh -`

### Backends

| Flag | API | Typical tables / columns |
|------|-----|---------------------------|
| *(default)* `-b app-insights` | `az monitor app-insights query` | `traces`, `requests`, `exceptions` — `timestamp`, `message` |
| `-b workspace` | `az monitor log-analytics query` | `AppTraces`, `AppExceptions` — `TimeGenerated`, `Message` |

Workspace **customer ID** is resolved automatically from `AZURE_RESOURCE_GROUP` + `LOG_ANALYTICS_WORKSPACE_NAME`, unless you set `LOG_ANALYTICS_WORKSPACE_ID`.

### Useful flags

- `-o table` — readable table (default is `jsonc`).
- `--offset 24h` — app-insights time window (default `7d`).
- `-t P3D` — workspace timespan (default `P7D`).
- `run_kql.sh --help`

### Windows / PowerShell

Multi-word **`-q '…|…'`** is often split incorrectly by PowerShell. Prefer:

- a **`.kql` file** and `run_kql.sh scripts/kql/your_query.kql`, or  
- **Git Bash / WSL** for inline `-q`, or  
- **stdin**: `Get-Content .\scripts\kql\foo.kql -Raw | docker compose … run --rm -i -T dev bash /workspace/scripts/run_kql.sh -`

---

## Structured bot events

| Prefix | Meaning |
|--------|---------|
| **`RAG_TURN_AUDIT`** | One JSON payload per completed turn (user text, answer, `needs_rag`, Pinecone fields, `azure_invocation_id`, …). |
| **`TEAMS_TURN_LATENCY`** | Per-step timings for the same turn; **`trace_id`** equals **`azure_invocation_id`**. Use `turn_latency_by_trace.kql` (set `trace_id` in the file). |

Example — latest audit row (app-insights):

```bash
docker compose -f docker-compose.dev.yml run --rm -T dev bash /workspace/scripts/run_kql.sh scripts/kql/last_rag_turn.kql
```

---

## Bundled `.kql` sketches

| File | Purpose |
|------|---------|
| `last_rag_turn.kql` | Latest `RAG_TURN_AUDIT` row (summary columns). |
| `dev_recent_turns_and_stops.kql` | Dev: audits + user-stopped stream + `finish_reason=length` lines (**`-b workspace -t P2D`**). |
| `recent_conversation_with_rag_decisions.kql` | Per-turn timeline of `RAG_TURN_AUDIT` (user message, optimized query, scope, `n_docs`, answer preview). Spot turns that fired RAG when history would have answered. |
| `optimizer_reuse_rate.kql` | Cache-aware optimizer monitoring: presence rate of cached retrieval shown to optimizer, distribution of `reuse_previous_context` decisions (none / reuse / augment), and avg cache age. |
| `investigate_appear_delay.kql` | Per-turn appear-delay breakdown from `turn_begin` to first informative POST. |
| `rent_payment_audit.kql` | Recent rent / pay / “How to” audits (app-insights). |
| `rag_audit_ukrainian_rent.kql` | Ukrainian-rent keyword slice (**`-b workspace`**). |
| `turn_latency_by_trace.kql` | All `TEAMS_TURN_LATENCY` steps for one `trace_id` / invocation. |
| `recent_rag_audit.kql` | Sample recent audits (workspace schema — use `-b workspace`). |
| `recent_exceptions.kql` | Recent `AppExceptions` (**`-b workspace`**). |
| `appinsights_process_errors.kql` | `process_message` errors in **`AppTraces`** (**`-b workspace`**, e.g. `-t P1D`). |

Add your own files under `scripts/kql/`; full-line `//` comments are stripped before the query runs.

---

## Optional: snapshot file under `logs/`

**`scripts/fetch-azure-logs.sh`** runs a few fixed queries and `az webapp log show` metadata, writing **`logs/azure-fetch-<timestamp>.log`** (git-ignored). Use when you want a **local file** without crafting KQL.

```bash
docker compose -f docker-compose.dev.yml run --rm dev bash /workspace/scripts/fetch-azure-logs.sh
```

Optional env: `AZURE_RESOURCE_GROUP`, `AZURE_APP_INSIGHTS_NAME`, `AZURE_FUNCTION_APP_NAME`, `AZURE_LOG_OUT_DIR`.

---

## Other scripts (not Application Insights)

Conversation **Table Storage** helpers (`summarize_conversations_table.sh`, `query_conversations_table.sh`, `export_conversations_partition.sh`, …) are documented near the top of **[`scripts/README.md`](../README.md)**. They are separate from log analytics.

---

## Portal

You can always run the same Kusto in Azure Portal → Application Insights → **Logs**, or Log Analytics → **Logs**. The repo workflow exists so you can **repeat queries from Git** without copy-paste.
