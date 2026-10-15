# LibreChat soft-fork config (Phase 0 / 2)



Config-only soft fork for the Office IDE web shell. The RAG core is **not** LibreChat’s bundled `rag_api` — it is our OpenAI-compatible adapter under `teams-bot/web/`.



| Doc | Purpose |

|-----|---------|

| [LIBRECHAT-SPIKE.md](../docs/office-ide/LIBRECHAT-SPIKE.md) | Spike checklist (OIDC, SSE, Mongo, legal) |

| [FRONTEND-EXIT-CRITERIA.md](../docs/office-ide/FRONTEND-EXIT-CRITERIA.md) | When to leave LibreChat for a custom UI |

| [HOSTING-ADAPTER.md](../docs/office-ide/HOSTING-ADAPTER.md) | Why FastAPI sidecar vs Functions |

| [LIBRECHAT-HOSTING.md](../infrastructure/docs/LIBRECHAT-HOSTING.md) | **Phase 2:** ACA + Mongo + Entra env wiring (Terraform stubs) |



## Prerequisites



1. **RAG adapter** running locally (Phase 1):



   ```bash

   cd teams-bot

   # set OPENAI_*, PINECONE_*, RAG_WEB_API_KEY (see teams-bot README)

   python -m web.app

   # listens on http://127.0.0.1:8081  →  /v1/models , /v1/chat/completions

   ```



2. MongoDB for LibreChat (local Docker or Atlas/Cosmos — decide in the spike; see LIBRECHAT-SPIKE.md §8).

3. LibreChat upstream image/source (pin a release tag; do not vendor the whole tree into this repo yet).



## Wire config



```bash

cp librechat/.env.example /path/to/LibreChat/.env

# edit secrets; set RAG_WEB_API_KEY to the same value as the adapter

cp librechat/librechat.yaml /path/to/LibreChat/librechat.yaml

```



In Docker Desktop / Compose, `host.docker.internal:8081` reaches the adapter on the host. On Linux you may need `extra_hosts` or the host gateway IP.



## Smoke



1. Open LibreChat → Entra login (when configured) or local auth for pure adapter tests.

2. Select **Northwind Residences RAG** / `ragstone` (should be the only model).

3. Ask a short PL question; confirm streaming + status (thinking) + **Źródła** markdown.

4. Check adapter logs for `RAG_TURN_AUDIT` with `"channel": "web"`.



## Deploy to Azure Container Apps (Phase 2)



Terraform scaffolding lives under `infrastructure/` (same stack as the Teams bot). **Default is off** so existing Function App plans are unchanged.



| Piece | Path |

|-------|------|

| Hosting guide (Mongo options, Entra, secrets) | [`infrastructure/docs/LIBRECHAT-HOSTING.md`](../infrastructure/docs/LIBRECHAT-HOSTING.md) |

| ACA + LibreChat stubs | [`infrastructure/librechat.tf`](../infrastructure/librechat.tf) |

| Variables / outputs | [`infrastructure/variables.tf`](../infrastructure/variables.tf), [`outputs.tf`](../infrastructure/outputs.tf) |

| tfvars comments | `infrastructure/environments/{dev,prod}.tfvars` |



**Enable (dev first, after human gates):**



1. Record Mongo choice in spike doc; register Entra OIDC app + app role.

2. Build/push soft-fork image; set `librechat_image` and `librechat_rag_adapter_base_url` (`…/v1`).

3. Set `librechat_enabled = true` and OIDC non-secret vars in tfvars; pass secrets only via `TF_VAR_*` / Key Vault.

4. Use deployment-ops: `./scripts/terraform.sh dev plan` then `apply` — do **not** apply from this README alone.



Update `librechat.yaml` `baseURL` for the ACA adapter URL (not `host.docker.internal`) before baking the image or mounting config.



Pilot runs alongside Teams prod; do not mark task **39** complete until user smoke confirms.

## Phase 3 MCP plugins

Stub MCP servers: [`../mcp-plugins/`](../mcp-plugins/). Example LibreChat registration (commented): [`mcp-servers.example.yaml`](mcp-servers.example.yaml). Do not enable live Graph until Entra consent + OBO smoke.

