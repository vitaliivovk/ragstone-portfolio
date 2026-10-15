# Real-estate vertical (on the flexible core)

Domain packaging for property / rental operations (e.g. Northwind-style clients). **No vertical-specific runtime is required** — processes and connectors sit on the same Office IDE core.

## What is core (shared)

| Piece | Role |
|-------|------|
| RAG service + OpenAI-compatible facade | Polish Q&A over tenant Pinecone corpus |
| LibreChat (or later custom shell) | Chat + curated agents |
| MCP plugins | SharePoint, Teams, Outlook, Salesforce, … |
| Process engine | Versioned definitions → draft artifacts (never auto-send in v1) |
| Conversation mining | Promote recurring patterns into process sketches |

## What is vertical (config + catalog)

- **Corpus / namespaces** — lease, ops, handbook folders already live in the KB pipeline; vertical = which folders and routing prompts ship per client.
- **Curated agents** — LibreChat agents that bind RAG + allowed MCP tools for roles (front desk, ops, finance).
- **Process catalog entries** — YAML/JSON definitions under the process engine, versioned per tenant or shared templates.
- **Connector enablement** — which MCP servers and Graph/Salesforce scopes that customer consents to.

No fork of the RAG graph for “real estate mode.” Prefer catalog + policy.

## Example future processes (not implemented)

Illustrative only — do not treat as a backlog commitment:

1. **Lease packet assemble** — inputs: property id, tenant name; steps: RAG for template clauses + SharePoint pull of signed lease / annexes + LLM transform into a checklist packet; output: draft email or SharePoint staging folder (**draft / never send**).
2. **Handover checklist** — inputs: unit id, move-in date; steps: Salesforce/CRM lookup (keys, meters) + SharePoint ops SOP + RAG FAQ; output: structured checklist artifact for human sign-off.
3. **Standard client reply** (already sketched in process-engine) — gather from corpus + optional CRM; compose fixed-format email **draft** via Outlook plugin.

Promote discovered patterns via mining ([`PROCESS-MINING.md`](PROCESS-MINING.md)) rather than hard-coding vertical logic in the bot.

## Connectors that matter early

| Connector | Typical real-estate use |
|-----------|-------------------------|
| SharePoint | Contracts, SOPs, photo packs under `AI/` mirrors |
| Teams | Internal ops threads (read/draft) |
| Outlook | Client-facing drafts from processes |
| Salesforce (or other CRM) | Property / contact / case lookup |

## Boundary with the Teams bot

Teams remains a **channel** into the same RAG core. Vertical processes should be authored once and exposed via MCP / curated agents so web and (later) Teams agents share definitions.
