# Development Environment Configuration
# Deploy to: dev Azure tenant
#
# tenant_id / subscription_id are NOT committed. Supply them from the environment:
#   .env → DEV_AZURE_TENANT_ID / DEV_AZURE_SUBSCRIPTION_ID (scripts/terraform.sh exports TF_VAR_*)
#   or export TF_VAR_tenant_id / TF_VAR_subscription_id directly.

environment = "dev"
location    = "westeurope"
# Bot queries this namespace; pipeline upserts to PINECONE_NAMESPACE_DEV + PINECONE_NAMESPACE_PROD
pinecone_index_name = "text-embedding-3-small"
pinecone_namespace  = "v3"

# Citation links: SharePoint mirror under AI/dev (prod uses AI/prod)
sharepoint_library_base_url = "https://contoso.sharepoint.com/sites/Northwind-AI/Shared%20Documents/AI/dev"

openai_model           = "gpt-5-mini"
openai_optimizer_model = "gpt-5-nano"
openai_embedding_model = "text-embedding-3-small"

# LibreChat / ACA (Phase 2) — keep disabled until Entra + Mongo + image are ready.
# Secrets: TF_VAR_librechat_openid_client_secret, TF_VAR_librechat_openid_session_secret,
# TF_VAR_librechat_mongo_uri, TF_VAR_librechat_rag_web_api_key (never commit).
# Docs: infrastructure/docs/LIBRECHAT-HOSTING.md
# librechat_enabled              = false
# librechat_mongo_provider       = "none" # cosmos_vcore | atlas after spike
# librechat_openid_issuer        = "https://login.microsoftonline.com/<TENANT_ID>/v2.0"
# librechat_openid_client_id     = ""
# librechat_openid_required_role = "Northwind.AI.User"
# librechat_rag_adapter_base_url = "https://<rag-adapter-host>/v1"
# librechat_custom_domain        = ""
# librechat_image                = "<acr>.azurecr.io/librechat:<tag>"
