# LibreChat hosting (Azure Container Apps)

Phase 2 scaffolding for the Office IDE web shell. Soft-fork LibreChat (own image) runs on **Azure Container Apps (ACA)** next to (or pointing at) the RAG OpenAI-compatible adapter. Teams bot / Functions stay unchanged.

**Status:** Terraform stubs only (`librechat_enabled = false` by default). Do **not** `terraform apply` until Entra app registration, Mongo choice, and image registry are ready.

| Related | Location |
|---------|----------|
| Spike checklist | [`docs/office-ide/LIBRECHAT-SPIKE.md`](../../docs/office-ide/LIBRECHAT-SPIKE.md) |
| Adapter hosting | [`docs/office-ide/HOSTING-ADAPTER.md`](../../docs/office-ide/HOSTING-ADAPTER.md) |
| Config scaffold | [`librechat/README.md`](../../librechat/README.md) |
| TF stubs | [`../librechat.tf`](../librechat.tf), variables in [`../variables.tf`](../variables.tf) |
| Task | [`docs/TASKS.md`](../../docs/TASKS.md) #39 |

## Architecture (target)

```
Browser → ACA ingress (custom domain + TLS)
            → LibreChat container (soft-fork image)
                 ├─ Mongo (Cosmos Mongo vCore OR Atlas EU) — conversation history
                 ├─ Entra OIDC (tenant lock + OPENID_REQUIRED_ROLE)
                 └─ HTTP → RAG adapter (/v1/chat/completions SSE)
                              ├─ same ACA (sidecar / second container app), OR
                              └─ URL to FastAPI on ACA / elsewhere (not Functions SSE)
```

Log Analytics: reuse existing `azurerm_log_analytics_workspace.main` (same pattern as Application Insights for Functions).

## Enablement (when ready to apply)

1. Human completes Entra OIDC app registration (see below).
2. Spike decides Mongo provider; record in LIBRECHAT-SPIKE.md §8.
3. Build/push LibreChat soft-fork image to ACR (or pin a private registry).
4. Set in tfvars / `TF_VAR_*` (never commit secrets):

```hcl
librechat_enabled              = true
librechat_image                = "<acr>.azurecr.io/librechat:<tag>"
librechat_openid_issuer        = "https://login.microsoftonline.com/<TENANT_ID>/v2.0"
librechat_openid_client_id     = "<app-client-id>"
librechat_openid_required_role = "Northwind.AI.User"
librechat_rag_adapter_base_url = "https://<rag-adapter-host>/v1"
# secrets via TF_VAR_librechat_openid_client_secret, TF_VAR_librechat_mongo_uri, TF_VAR_librechat_rag_web_api_key, …
librechat_custom_domain        = "ai.example.com"  # optional; leave empty for *.azurecontainerapps.io
```

5. `./scripts/terraform.sh <env> plan` then `apply` (deployment-ops skill). Prefer **dev** first.

## Terraform resources (repo style)

Flat `.tf` files under `infrastructure/`, same RG / tags / `local.base_name` as Functions:

| Resource | Name pattern | Notes |
|----------|--------------|-------|
| `azurerm_container_app_environment` | `cae-${local.base_name}` | Links to existing Log Analytics |
| `azurerm_container_app` (LibreChat) | `ca-librechat-${local.base_name}` | Image placeholder; ingress 3080 |
| Optional later | `ca-rag-web-…` | FastAPI adapter sidecar in same environment |
| Custom domain | `azurerm_container_app_custom_domain` | After managed cert / DNS — stubbed as variables only for now |

Gated with `count = var.librechat_enabled ? 1 : 0` so default `plan` does not create ACA.

Secrets follow Key Vault + ACA secret refs (same idea as Function App `@Microsoft.KeyVault(...)`): store in Key Vault, wire ACA `secret { key_vault_secret_id = … }` once identity access policies exist. Scaffolding uses ACA `secret` blocks fed by **sensitive Terraform variables** so nothing lands in git; promote to Key Vault secrets before prod.

### Env wiring (LibreChat container)

| Env / secret | Source | In git? |
|--------------|--------|---------|
| `OPENID_ISSUER`, `OPENID_CLIENT_ID`, `OPENID_REQUIRED_ROLE`, `OPENID_SCOPE`, … | Non-sensitive TF variables | IDs/issuer OK in tfvars |
| `OPENID_CLIENT_SECRET`, `OPENID_SESSION_SECRET` | Sensitive TF vars → ACA secrets / Key Vault | **Never** |
| `MONGO_URI` | Sensitive; from Cosmos connection string or Atlas | **Never** |
| `RAG_WEB_API_KEY` | Same value as adapter `RAG_WEB_API_KEY` | **Never** |
| `DOMAIN_CLIENT` / `DOMAIN_SERVER` | Derived from custom domain or ACA FQDN | hostname only |
| Custom endpoint `baseURL` | `librechat.yaml` baked in image **or** config mount; points at `librechat_rag_adapter_base_url` | URL only |

Adapter URL options:

1. **Separate ACA** for `teams-bot/web` FastAPI (preferred for SSE) — set `librechat_rag_adapter_base_url` to that app’s HTTPS URL (`…/v1`).
2. **Same environment, internal ingress** — use ACA internal FQDN once both apps exist.
3. **Do not** point LibreChat at Azure Functions for SSE (see HOSTING-ADAPTER.md).

## MongoDB options

Choose one after Phase 0 spike (LIBRECHAT-SPIKE.md §8). Terraform approach for each:

### A. Cosmos DB for MongoDB vCore (Azure-native, preferred if compat OK)

- Resource family: `azurerm_cosmosdb_mongo_cluster` (vCore) + connection string secret — provider API evolves; confirm exact resource against pinned `azurerm ~> 3.x` before un-commenting.
- Same subscription/tenant billing; EU region aligned with `var.location` (e.g. `westeurope` / `polandcentral`).
- **Spike must prove** LibreChat migrations + conversation CRUD against the cluster’s Mongo wire version.
- Stub: commented block in [`librechat.tf`](../librechat.tf); set `librechat_mongo_provider = "cosmos_vcore"` and pass `librechat_mongo_uri` from the cluster output once live.

### B. MongoDB Atlas (EU fallback)

- No Azure resource in this repo — create Atlas cluster (EU region) out of band; store connection string in Key Vault / `TF_VAR_librechat_mongo_uri`.
- Requires customer-acceptable DPA for third-party Mongo.
- Set `librechat_mongo_provider = "atlas"`; Terraform only consumes the URI secret.

### C. Deferred / none

- `librechat_mongo_provider = "none"` — ACA stubs can still plan for image/ingress; LibreChat will not start without a real URI.

**Sizing (~100 users):** smallest Mongo tier; LibreChat ~2× 0.5–1 vCPU for redundancy (not load). Bottleneck remains LLM latency. Rough add-on infra ~$150–300/mo per client (roadmap estimate).

## Ingress / custom domain

1. Default: external ACA ingress → `*.azurecontainerapps.io` (dev/spike).
2. Production: DNS CNAME to ACA FQDN; managed certificate + `azurerm_container_app_custom_domain` (enable when `librechat_custom_domain` is set — resource still TODO after first successful default ingress).
3. TLS termination on ACA; `https_only` / `allow_insecure_connections = false`.

## Entra app registration (human)

Not automated in Terraform yet (bot app registration exists in `bot.tf`; LibreChat is a **separate** web OIDC client):

1. App registration (single-tenant), redirect URIs for LibreChat (`https://<domain>/oauth/openid/callback` — confirm exact path for pinned LibreChat version).
2. Client secret → Key Vault / `TF_VAR_librechat_openid_client_secret`.
3. App role e.g. `Northwind.AI.User`; assign users/groups; set `OPENID_REQUIRED_ROLE`.
4. Optional SharePoint picker: delegated `Files.Read.All`, `AllSites.Read`, `access_as_user`; `OPENID_REUSE_TOKENS=true`.
5. `ALLOW_REGISTRATION=false`.

## Optional later (same ACA environment)

- Meilisearch container (LibreChat search) — skip at pilot scale if unused.
- Redis — skip at this scale.
- MCP plugin containers + process engine (Phases 3–4).
- RAG adapter container app (duplicate OpenAI/Pinecone env from Functions via Key Vault).

## Explicit non-goals for this scaffolding pass

- No `terraform apply` / Azure deploy from agents without deployment-ops + human approve.
- No secrets in git or tfvars committed to the repo.
- No Cosmos/Atlas cluster creation until Mongo spike decision is recorded.
