# Frontend exit criteria (LibreChat → custom)

When to leave the LibreChat **soft-fork** for a custom frontend. Adapter + MCP remain shell-independent either way.

## Stay on LibreChat when

- Chat + curated agents + SharePoint picker cover the pilot.
- Soft-fork stays config/theming/MCP + small additive patches only.
- Document-side-by-side / process forms are not yet required (Phase 5 gate).

## Exit triggers (any one is enough)

1. **Patch budget** — more than ~**6 meaningful** upstream patches (not YAML/env), or rebases become painful every release.
2. **Document IDE UX** — product needs side-by-side document viewer, citation click-through into a pane, or process/workflow forms that cannot be done with curated agents + MCP without forking LibreChat’s React client.
3. **Multi-tenant SaaS** — LibreChat has no real tenancy; custom shell required for admin dashboard + per-tenant isolation UI.
4. **Hard-fork creep** — team is editing LibreChat core for routing, streaming, or RAG instead of using the OpenAI-compatible facade.

## What stays after exit

- RAG OpenAI-compatible facade (`teams-bot/web/`)
- MCP plugins (SharePoint, Teams, …)
- Process/workflow engine
- Entra OIDC / OBO patterns
- `RAG_TURN_AUDIT` + conversation mining inputs

## What is rebuilt

- Chat UI and history UX (LibreChat Mongo history may be migrated or dual-read during transition)
- Agent marketplace / builder affordances (if any) → our curated catalog

## Decision owner

Product + engineering review at **Phase 5** (conversation mining + frontend gate). Record go/no-go in this file or TASKS.md task **39**.

**Related (same phase):** conversation mining inputs and promote-to-process flow — [`PROCESS-MINING.md`](PROCESS-MINING.md).
