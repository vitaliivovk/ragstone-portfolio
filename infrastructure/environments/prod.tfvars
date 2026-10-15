# Production Environment Configuration — customer Azure tenant
#
# tenant_id / subscription_id are NOT committed. Supply them from the environment:
#   .env → PROD_AZURE_TENANT_ID / PROD_AZURE_SUBSCRIPTION_ID (scripts/terraform.sh exports TF_VAR_*)
#   or export TF_VAR_tenant_id / TF_VAR_subscription_id directly.
#
# Before apply/deploy, verify:
# - TF_VAR_tenant_id / TF_VAR_subscription_id match the production Azure AD + subscription (not dev).
# - `.env` used for Terraform loads OPENAI_API_KEY / PINECONE_API_KEY for this stack (or TF_VAR_*).
# - Pipeline indexing: PINECONE_NAMESPACE_PROD=production (same as `pinecone_namespace` below) and
#   same `pinecone_index_name` so the bot queries vectors you actually upserted.
# - Bot is Single-tenant: MICROSOFT_APP_TENANT_ID in Terraform = `tenant_id`.

environment = "prod"
location    = "polandcentral"

pinecone_index_name = "text-embedding-3-small"
pinecone_namespace  = "production"

# Citation links: corpus mirror under AI/prod (dev stack uses AI/dev)
sharepoint_library_base_url = "https://contoso.sharepoint.com/sites/Northwind-AI/Shared%20Documents/AI/prod"

openai_model           = "gpt-5-mini"
openai_optimizer_model = "gpt-5-nano"
openai_embedding_model = "text-embedding-3-small"

# LibreChat / ACA (Phase 2) — enable on prod only after successful dev pilot.
# Secrets via TF_VAR_* / Key Vault only. See infrastructure/docs/LIBRECHAT-HOSTING.md
# librechat_enabled              = false
# librechat_mongo_provider       = "none"
# librechat_openid_issuer        = "https://login.microsoftonline.com/<PROD_TENANT_ID>/v2.0"
# librechat_openid_client_id     = ""
# librechat_openid_required_role = "Northwind.AI.User"
# librechat_rag_adapter_base_url = "https://<rag-adapter-host>/v1"
# librechat_custom_domain        = ""
# librechat_image                = "<acr>.azurecr.io/librechat:<tag>"
