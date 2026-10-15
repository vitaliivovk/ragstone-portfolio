variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be 'dev' or 'prod'."
  }
}

variable "tenant_id" {
  description = "Azure AD Tenant ID for this deployment. Supply via TF_VAR_tenant_id (scripts/terraform.sh maps DEV_/PROD_AZURE_TENANT_ID from .env); not committed in tfvars."
  type        = string
}

variable "subscription_id" {
  description = "Azure Subscription ID for this deployment. Supply via TF_VAR_subscription_id (scripts/terraform.sh maps DEV_/PROD_AZURE_SUBSCRIPTION_ID from .env); not committed in tfvars."
  type        = string
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "westeurope"
}

variable "project_name" {
  description = "Project name used in resource naming"
  type        = string
  default     = "northwind"
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}

variable "pinecone_api_key" {
  description = "Pinecone API key"
  type        = string
  sensitive   = true
}

variable "pinecone_index_name" {
  description = "Pinecone index name"
  type        = string
  default     = "text-embedding-3-small"
}

variable "pinecone_namespace" {
  description = "Pinecone namespace"
  type        = string
  default     = "v3"
}

variable "sharepoint_library_base_url" {
  description = "SharePoint document library folder URL mirroring pinecone source_data (citation links: base + sourceRelativePath). Leave empty to omit."
  type        = string
  default     = ""
}

variable "openai_model" {
  description = "OpenAI chat model for Teams bot answer generation"
  type        = string
  default     = "gpt-5-mini"
}

variable "openai_optimizer_model" {
  description = "OpenAI chat model for RAG optimizer (structured routing)"
  type        = string
  default     = "gpt-5-nano"
}

variable "openai_embedding_model" {
  description = "OpenAI embedding model (must match Pinecone index dimensions)"
  type        = string
  default     = "text-embedding-3-small"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# -----------------------------------------------------------------------------
# LibreChat / Azure Container Apps (Phase 2 — scaffolding; default off)
# See infrastructure/docs/LIBRECHAT-HOSTING.md
# -----------------------------------------------------------------------------

variable "librechat_enabled" {
  description = "When true, create ACA environment + LibreChat container app. Keep false until Entra/Mongo/image are ready."
  type        = bool
  default     = false
}

variable "librechat_image" {
  description = "LibreChat soft-fork container image (ACR or other registry). Placeholder until first build."
  type        = string
  default     = "ghcr.io/danny-avila/librechat:latest"
}

variable "librechat_cpu" {
  description = "vCPU for LibreChat container"
  type        = number
  default     = 0.5
}

variable "librechat_memory" {
  description = "Memory for LibreChat container (e.g. 1Gi)"
  type        = string
  default     = "1Gi"
}

variable "librechat_custom_domain" {
  description = "Optional custom hostname (e.g. ai.customer.com). Empty = use ACA default FQDN only; custom domain resource still commented in librechat.tf."
  type        = string
  default     = ""
}

variable "librechat_openid_issuer" {
  description = "Entra OIDC issuer (tenant-specific), e.g. https://login.microsoftonline.com/<TENANT_ID>/v2.0"
  type        = string
  default     = ""
}

variable "librechat_openid_client_id" {
  description = "Entra app (client) ID for LibreChat OIDC — not a secret"
  type        = string
  default     = ""
}

variable "librechat_openid_required_role" {
  description = "Entra app role / group claim required to use the web shell"
  type        = string
  default     = "Northwind.AI.User"
}

variable "librechat_openid_scope" {
  description = "OIDC scopes for LibreChat"
  type        = string
  default     = "openid profile email offline_access"
}

variable "librechat_openid_button_label" {
  description = "Login button label (PL)"
  type        = string
  default     = "Zaloguj kontem firmowym"
}

variable "librechat_openid_client_secret" {
  description = "Entra client secret for LibreChat OIDC. Pass via TF_VAR_ only — never commit."
  type        = string
  sensitive   = true
  default     = ""
}

variable "librechat_openid_session_secret" {
  description = "LibreChat OPENID_SESSION_SECRET. Pass via TF_VAR_ only — never commit."
  type        = string
  sensitive   = true
  default     = ""
}

variable "librechat_mongo_provider" {
  description = "Mongo hosting choice after spike: none | cosmos_vcore | atlas (resources commented until chosen)"
  type        = string
  default     = "none"

  validation {
    condition     = contains(["none", "cosmos_vcore", "atlas"], var.librechat_mongo_provider)
    error_message = "librechat_mongo_provider must be none, cosmos_vcore, or atlas."
  }
}

variable "librechat_mongo_uri" {
  description = "Mongo connection string for LibreChat. Pass via TF_VAR_ only — never commit."
  type        = string
  sensitive   = true
  default     = ""
}

variable "librechat_rag_adapter_base_url" {
  description = "OpenAI-compatible RAG adapter base URL ending in /v1 (ACA FastAPI sidecar or separate host — not Functions SSE)"
  type        = string
  default     = ""
}

variable "librechat_rag_web_api_key" {
  description = "Bearer API key shared by LibreChat and the RAG adapter. Pass via TF_VAR_ only — never commit."
  type        = string
  sensitive   = true
  default     = ""
}

variable "librechat_deploy_rag_adapter" {
  description = "Future: create RAG adapter container app in the same ACA environment (stub commented in librechat.tf)"
  type        = bool
  default     = false
}

locals {
  base_name = "${var.project_name}-${var.environment}"

  default_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
  }

  tags = merge(local.default_tags, var.tags)
}
