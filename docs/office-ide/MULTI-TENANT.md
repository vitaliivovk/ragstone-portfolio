# Multi-tenant model (Office IDE)

How tenancy works while LibreChat is the shell, and what changes for true SaaS.

## Principles

- **Isolation from day one:** every request carries a `tenant_id` (customer id). Pinecone namespace, secrets, and audit lines are scoped by it.
- **Deploy-per-client today:** LibreChat has **no real multi-tenancy**. Each customer gets their own LibreChat + Mongo (+ later MCP/process containers) — typically one Azure subscription / resource group module.
- **SaaS multi-tenancy later** requires the **custom frontend** exit ([`FRONTEND-EXIT-CRITERIA.md`](FRONTEND-EXIT-CRITERIA.md) trigger #3): shared control plane, admin dashboard, usage analytics, and tenant switch UI.

## Identity: `tenant_id`

| Layer | Source of truth |
|-------|-----------------|
| Web (LibreChat) | Entra **tenant** (issuer) + optional app claim / config map → internal `tenant_id` |
| Teams bot | Existing per-customer Function App / config (same internal id) |
| RAG adapter | Header or config default; stamp on `RAG_TURN_AUDIT` |
| MCP plugins | Forward `X-Tenant-ID` (or derive from token `tid`); never cross-query |
| Process engine | Catalog may be shared templates; **runs** and secrets are tenant-scoped |
| Pinecone | One **namespace per tenant** (e.g. `v3` / `production` today map to a single client; multi-client = distinct namespaces or indexes) |

Do not reuse Teams `29:…` ids as web user keys. Cross-channel state is optional and needs an explicit AAD-oid map.

## Per-client LibreChat deploy

Repeatable Terraform module (see [`LIBRECHAT-HOSTING.md`](../../infrastructure/docs/LIBRECHAT-HOSTING.md)):

- ACA (or equivalent) + LibreChat image
- Mongo (Cosmos vCore or Atlas EU) — **conversation history stays in that customer’s DB**
- Entra app registration **in the customer’s tenant** (issuer lock, `OPENID_REQUIRED_ROLE`)
- RAG adapter URL + API key for that environment
- Optional MCP plugin containers pointing at that customer’s Graph / Salesforce

Cost model: ~one shell stack per client until custom frontend.

## Pinecone namespaces

- Index may be shared or dedicated; **namespace (or index) must not leak across tenants**.
- Corpus sync / `kb.sh` already assumes per-environment namespaces; multi-tenant ops must pass `tenant_id` → namespace mapping explicitly.
- Citations and SharePoint paths remain customer-estate-specific.

## Entra per customer

| Concern | Pattern |
|---------|---------|
| Login | Tenant-specific `OPENID_ISSUER`; `ALLOW_REGISTRATION=false` |
| Authorization | App roles / groups → `OPENID_REQUIRED_ROLE`; replaces Teams display-name allowlist for web |
| Data access | OBO into **that** customer’s Graph (SharePoint, Teams, Outlook) |
| Salesforce | Separate Connected App + secrets **per tenant** (not Entra OBO) |
| Admin consent | Customer IT grants delegated (and optional `Sites.Selected`) in their tenant |

Never point a prod LibreChat at a different customer’s Entra issuer or Graph.

## What requires a custom frontend (SaaS)

LibreChat soft-fork is fine for **single-tenant pilots**. Move to a custom shell when you need:

- One deployment serving many tenants with isolation UI
- Cross-tenant admin dashboard / billing / usage analytics
- Tenant provisioning UX without spinning a full LibreChat stack each time
- Document-IDE features that already trip the Phase 5 exit gate

Adapter, MCP, process engine, and mining stay; only the chat shell is replaced.

## Audit and mining

- `RAG_TURN_AUDIT` and `MCP_TOOL_AUDIT` include `tenant_id`.
- Conversation mining runs **per tenant** (no cross-tenant clustering).
- Retention/deletion follows that customer’s DPA / GDPR posture.
