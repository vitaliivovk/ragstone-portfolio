# Salesforce plugin stub

Lookup placeholders in [`server.py`](server.py). No live Salesforce API.

| Tool | Scope | Notes |
|------|-------|-------|
| `salesforce_search` | search | SOSL / global search when wired |
| `salesforce_lookup_record` | read | By Id or external id |
| `salesforce_list_related` | read | Child / related list |

**Auth:** per-tenant Connected App OAuth (refresh token), **not** Entra OBO. Store secrets per `tenant_id` — see [`docs/office-ide/MULTI-TENANT.md`](../../../docs/office-ide/MULTI-TENANT.md).

No create/update/delete in v1 stub. **Onyx harvest:** MIT Salesforce connector shapes only (exclude `ee/`).
