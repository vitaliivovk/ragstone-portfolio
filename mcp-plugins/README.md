# MCP plugins (Office IDE Phase 3 + 6)

Scaffolding for company-resource plugins exposed to LibreChat as **MCP servers** (streamable-http). The RAG core stays an OpenAI-compatible custom endpoint — MCP is for SharePoint, Teams, Outlook, Salesforce, and process wrappers only.

**Status:** code stubs + docs. No live Microsoft Graph / Salesforce calls. No admin consent required to run the local stubs.

| Path | Role |
|------|------|
| [`common/`](mcp_plugins/common/) | Scope policy + audit helpers (unit-tested) |
| [`template/`](mcp_plugins/template/) | Minimal stdlib HTTP MCP-shaped server (health + stub tools) |
| [`sharepoint/`](mcp_plugins/sharepoint/) | SharePoint list/browse/read tool signatures |
| [`teams/`](mcp_plugins/teams/) | Teams read/post placeholders |
| [`processes/`](mcp_plugins/processes/) | Phase 4 thin wrappers: `list_processes` / `run_process` (needs sibling `process-engine/`) |
| [`outlook/`](mcp_plugins/outlook/) | Phase 6 — mail search/read/draft; send denied in v1 |
| [`salesforce/`](mcp_plugins/salesforce/) | Phase 6 — CRM search/lookup placeholders (Connected App OAuth later) |
| [`tests/`](tests/) | Pure helper unit tests (no network) |

LibreChat registration example: [`../librechat/mcp-servers.example.yaml`](../librechat/mcp-servers.example.yaml).

Related backlog: TASKS **#14** / **#14c** (tool policy + Graph OBO), **#35** (`Sites.Selected` app grants for headless bot write), task **#39** Phases 3 + 6. Multi-tenant notes: [`docs/office-ide/MULTI-TENANT.md`](../docs/office-ide/MULTI-TENANT.md).

---

## Streamable-HTTP contract

LibreChat production MCP servers should use `type: streamable-http` (not long-lived SSE stdio for multi-user). Spec: [MCP transports — Streamable HTTP](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http).

This scaffold implements a **deliberately thin** JSON-RPC-over-HTTP surface so we can develop tools without pinning the full `mcp` Python SDK yet:

| Route | Method | Purpose |
|-------|--------|---------|
| `/health` | GET | Liveness (`{"status":"ok","plugin":"…"}`) |
| `/mcp` | POST | JSON-RPC: `initialize`, `tools/list`, `tools/call`, `ping` |

When wiring to LibreChat for real, either:

1. Swap the transport layer for the official Python MCP SDK (`mcp` package) while keeping `common/` policy + audit, or
2. Keep this handler if LibreChat’s streamable-http client accepts our responses after a spike.

**Do not** expose these stubs on a public URL without auth.

---

## Scope policy (server-enforced)

Every tool declares a scope. The server rejects calls outside the active policy **before** any Graph client runs.

| Scope | v1 default | Meaning |
|-------|------------|---------|
| `read` | allow | Fetch metadata or file/message content the caller may see |
| `search` | allow | Query / filter listings |
| `draft` | allow (opt-in per plugin) | Create drafts or staging artifacts; never deliver externally |
| `send` / `post` (live) | **deny** | No outbound mail/send or unrestricted channel post in v1 |

Aligned with TASKS **#14**: enforce in code + Graph permission scopes; admin/user policy later.

Helpers: `common.policy.ToolScope`, `enforce_scope`, `V1_DEFAULT_POLICY`.

---

## OBO notes (no live exchange in this scaffold)

Worker-facing data access (what the signed-in user can see) uses **Entra On-Behalf-Of**:

1. LibreChat holds the user’s access token (OIDC / `OPENID_REUSE_TOKENS`).
2. LibreChat MCP config can pass OBO via the `obo:` block (see upstream LibreChat `mcpServers` docs) or forward a short-lived Graph token in a header — **spike which pattern LibreChat supports for your pinned version**.
3. Plugin exchanges (or receives) a Graph token with **delegated** scopes only.
4. Never log raw tokens. Audit may include `user_oid`, `tenant_id`, tool name, HTTP status, path — not bodies.

**Headless bot write** (corpus sync, smoke upload without a user) is a **different** path: application permission **`Sites.Selected`** + per-site grant — see TASKS **#35**. Do not conflate OBO (user-delegated) with `Sites.Selected` (app-only).

---

## Audit line shape

Emit one structured log line per tool invocation (stdout or App Insights custom event later):

```json
{
  "event": "MCP_TOOL_AUDIT",
  "plugin": "sharepoint",
  "tool": "sharepoint_browse_folder",
  "scope": "read",
  "tenant_id": "<guid-or-empty>",
  "user_oid": "<entra-oid-or-empty>",
  "conversation_id": "<optional>",
  "status": "ok|denied|error|stub",
  "http_status": null,
  "duration_ms": 12,
  "detail": {"path": "AI/v3", "reason": "scope_denied"}
}
```

Rules: no file/message bodies, no bearer tokens, no Graph refresh tokens. Helper: `common.audit.format_mcp_tool_audit`.

---

## Harvest Onyx CE connectors (later — do not copy wholesale)

[Onyx](https://github.com/onyx-dot-app/onyx) (formerly Danswer) MIT **core** has connector implementations for SharePoint, Teams, Outlook, Salesforce. Use as a **code quarry**, not a dependency:

1. Identify the MIT-licensed connector module for the target system (exclude anything under `ee/`).
2. Extract **API shapes** (endpoints, pagination, auth header patterns) into our Graph/HTTP clients under `mcp-plugins/<name>/`.
3. Re-implement behind our MCP tools + scope policy + audit; do **not** vendor Onyx’s indexer, permission-sync, or vector pipeline (we keep Pinecone + our RAG).
4. Record source file + license note in the plugin README when harvesting.

---

## Local run (stubs only)

```bash
cd mcp-plugins
# With uv (recommended on Windows):
uv run --with pytest --python 3.12 python -m mcp_plugins.template.server   # :8090
# Or: set PYTHONPATH=. and use any Python 3.11+
python -m mcp_plugins.sharepoint.server   # :8091
python -m mcp_plugins.teams.server        # :8092
# Phase 4 (after: pip install -e ../process-engine):
python -m mcp_plugins.processes.server    # :8093
# Phase 6:
python -m mcp_plugins.outlook.server      # :8094
python -m mcp_plugins.salesforce.server   # :8095
```

```bash
curl -s http://127.0.0.1:8090/health
curl -s -X POST http://127.0.0.1:8090/mcp -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}"
```

Tests (no network):

```bash
cd mcp-plugins
uv run --with pytest --python 3.12 pytest tests -q
```

---

## Next steps (real Graph consent)

See the Phase 3 checklist at the end of this README’s companion note in task **#39**, or:

1. Decide: extend bot app registration vs dedicated “MCP integrations” Entra app.
2. Admin: delegated Graph scopes for OBO (SharePoint/Teams read first) + consent.
3. Admin (optional headless write): TASKS **#35** `Sites.Selected` + per-site grant.
4. Implement MSAL OBO / client-credentials behind feature flags; keep stubs until smoke passes.
5. Register servers in LibreChat `mcpServers` and restrict which curated agents may call them.
