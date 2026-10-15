# LibreChat web shell — Azure Container Apps (Phase 2 scaffolding)
#
# Gated by var.librechat_enabled (default false). Safe for existing terraform plan/apply
# of Teams/Functions infra. See infrastructure/docs/LIBRECHAT-HOSTING.md.
#
# Do NOT enable + apply until: Entra OIDC app, Mongo choice, and container image are ready.

locals {
  librechat_domain_client = trimspace(var.librechat_custom_domain) != "" ? "https://${trimspace(var.librechat_custom_domain)}" : null
}

# -----------------------------------------------------------------------------
# Container Apps environment (shared later by LibreChat, RAG adapter, MCP)
# -----------------------------------------------------------------------------

resource "azurerm_container_app_environment" "librechat" {
  count = var.librechat_enabled ? 1 : 0

  name                       = "cae-${local.base_name}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  tags = local.tags
}

# -----------------------------------------------------------------------------
# LibreChat container app (soft-fork image placeholder)
# -----------------------------------------------------------------------------

resource "azurerm_container_app" "librechat" {
  count = var.librechat_enabled ? 1 : 0

  name                         = "ca-librechat-${local.base_name}"
  container_app_environment_id = azurerm_container_app_environment.librechat[0].id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  # Registry auth: add registry {} + pull secret when using private ACR.
  # Example:
  # registry {
  #   server               = var.librechat_registry_server
  #   username             = var.librechat_registry_username
  #   password_secret_name = "registry-password"
  # }

  template {
    min_replicas = var.environment == "prod" ? 2 : 1
    max_replicas = var.environment == "prod" ? 4 : 2

    container {
      name   = "librechat"
      image  = var.librechat_image
      cpu    = var.librechat_cpu
      memory = var.librechat_memory

      env {
        name  = "HOST"
        value = "0.0.0.0"
      }
      env {
        name  = "PORT"
        value = "3080"
      }
      env {
        name  = "ALLOW_REGISTRATION"
        value = "false"
      }
      env {
        name  = "ALLOW_EMAIL_LOGIN"
        value = "false"
      }
      env {
        name  = "NO_INDEX"
        value = "true"
      }

      # Entra OIDC — non-secret identifiers (issuer / client id / role name)
      env {
        name  = "OPENID_ISSUER"
        value = var.librechat_openid_issuer
      }
      env {
        name  = "OPENID_CLIENT_ID"
        value = var.librechat_openid_client_id
      }
      env {
        name  = "OPENID_REQUIRED_ROLE"
        value = var.librechat_openid_required_role
      }
      env {
        name  = "OPENID_SCOPE"
        value = var.librechat_openid_scope
      }
      env {
        name  = "OPENID_BUTTON_LABEL"
        value = var.librechat_openid_button_label
      }
      env {
        name  = "OPENID_REUSE_TOKENS"
        value = "true"
      }

      # Domains: custom hostname when set; else fill after first apply from ACA FQDN
      dynamic "env" {
        for_each = local.librechat_domain_client != null ? [1] : []
        content {
          name  = "DOMAIN_CLIENT"
          value = local.librechat_domain_client
        }
      }
      dynamic "env" {
        for_each = local.librechat_domain_client != null ? [1] : []
        content {
          name  = "DOMAIN_SERVER"
          value = local.librechat_domain_client
        }
      }

      # RAG adapter base URL (OpenAI-compatible /v1). Configure librechat.yaml baseURL to match.
      env {
        name  = "RAG_ADAPTER_BASE_URL"
        value = var.librechat_rag_adapter_base_url
      }

      # Secrets — values from sensitive TF vars / Key Vault (never commit). ACA secret name refs.
      env {
        name        = "OPENID_CLIENT_SECRET"
        secret_name = "openid-client-secret"
      }
      env {
        name        = "OPENID_SESSION_SECRET"
        secret_name = "openid-session-secret"
      }
      env {
        name        = "MONGO_URI"
        secret_name = "mongo-uri"
      }
      env {
        name        = "RAG_WEB_API_KEY"
        secret_name = "rag-web-api-key"
      }
    }
  }

  # Sensitive values: supply via TF_VAR_* or promote to azurerm_key_vault_secret + key_vault_secret_id.
  secret {
    name  = "openid-client-secret"
    value = var.librechat_openid_client_secret
  }
  secret {
    name  = "openid-session-secret"
    value = var.librechat_openid_session_secret
  }
  secret {
    name  = "mongo-uri"
    value = var.librechat_mongo_uri
  }
  secret {
    name  = "rag-web-api-key"
    value = var.librechat_rag_web_api_key
  }

  ingress {
    external_enabled           = true
    target_port                = 3080
    transport                  = "auto"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  tags = local.tags

  lifecycle {
    ignore_changes = [
      # Image tags often bumped by CI outside Terraform
      template[0].container[0].image,
    ]
  }
}

# -----------------------------------------------------------------------------
# Custom domain / TLS — placeholders (enable after default ingress works)
# -----------------------------------------------------------------------------
#
# 1. Create DNS CNAME: var.librechat_custom_domain → ACA FQDN (output librechat_fqdn)
# 2. Uncomment when ready (azurerm ~> 3.x names may vary slightly by provider patch):
#
# resource "azurerm_container_app_custom_domain" "librechat" {
#   count            = var.librechat_enabled && trimspace(var.librechat_custom_domain) != "" ? 1 : 0
#   name             = trimspace(var.librechat_custom_domain)
#   container_app_id = azurerm_container_app.librechat[0].id
#   # certificate_binding_type = "SniEnabled"
#   # container_app_environment_certificate_id = azurerm_container_app_environment_certificate.librechat[0].id
# }

# -----------------------------------------------------------------------------
# MongoDB — choose one after spike (LIBRECHAT-SPIKE.md §8); do not uncomment both
# -----------------------------------------------------------------------------
#
# Provider switch: var.librechat_mongo_provider = "cosmos_vcore" | "atlas" | "none"
# Atlas: no Azure resources — only set TF_VAR_librechat_mongo_uri from Atlas EU.
#
# Cosmos DB for MongoDB vCore (illustrative; confirm resource schema vs pinned azurerm):
#
# resource "azurerm_cosmosdb_mongo_cluster" "librechat" {
#   count               = var.librechat_enabled && var.librechat_mongo_provider == "cosmos_vcore" ? 1 : 0
#   name                = "mongo-${local.base_name}"
#   resource_group_name = azurerm_resource_group.main.name
#   location            = azurerm_resource_group.main.location
#   administrator_username = var.librechat_cosmos_admin_username
#   administrator_password = var.librechat_cosmos_admin_password  # sensitive TF_VAR_
#   shard_count            = 1
#   compute_tier           = "M30"   # spike: smallest viable LibreChat-compatible tier
#   high_availability_mode = "Disabled"
#   storage_size_in_gb     = 32
#   tags                   = local.tags
# }
#
# Then: set librechat_mongo_uri from the cluster connection string (Key Vault secret),
# or wire azurerm_key_vault_secret + ACA secret key_vault_secret_id.
#
# Optional Meilisearch / Redis containers: skip for pilot (~100 users). Same ACA env later.

# -----------------------------------------------------------------------------
# RAG adapter on ACA (optional second app) — Phase 2 follow-up
# -----------------------------------------------------------------------------
#
# Prefer FastAPI sidecar / second container app over Functions SSE (HOSTING-ADAPTER.md).
# Point librechat_rag_adapter_base_url at https://<ca-rag-web-fqdn>/v1 and bake
# librechat.yaml baseURL accordingly. Reuse Key Vault OpenAI/Pinecone secrets via
# user-assigned or system-assigned identity (mirror functions.tf pattern).
#
# resource "azurerm_container_app" "rag_web" {
#   count = var.librechat_enabled && var.librechat_deploy_rag_adapter ? 1 : 0
#   name  = "ca-rag-web-${local.base_name}"
#   ...
# }
