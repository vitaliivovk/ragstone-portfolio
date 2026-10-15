# App Service Plan (Consumption for cost-efficiency)
resource "azurerm_service_plan" "main" {
  name                = "asp-${local.base_name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = var.environment == "prod" ? "P1v2" : "Y1" # Y1 = Consumption

  tags = local.tags
}

# Azure Functions App
resource "azurerm_linux_function_app" "main" {
  name                = "func-${local.base_name}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.main.id

  storage_account_name       = azurerm_storage_account.functions.name
  storage_account_access_key = azurerm_storage_account.functions.primary_access_key

  https_only = true

  site_config {
    application_stack {
      python_version = "3.11"
    }

    cors {
      allowed_origins = ["https://portal.azure.com"]
    }

    # Required for async processing
    always_on = var.environment == "prod" ? true : false
  }

  app_settings = merge(
    {
      # Azure Functions settings
      FUNCTIONS_WORKER_RUNTIME       = "python"
      AzureWebJobsFeatureFlags       = "EnableWorkerIndexing"
      SCM_DO_BUILD_DURING_DEPLOYMENT = "1"

      # Bot Framework settings (SingleTenant requires tenant ID)
      MICROSOFT_APP_ID        = azuread_application.bot.client_id
      MICROSOFT_APP_PASSWORD  = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault_secret.bot_password.id})"
      MICROSOFT_APP_TYPE      = "SingleTenant"
      MICROSOFT_APP_TENANT_ID = var.tenant_id

      # OpenAI settings
      OPENAI_API_KEY         = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault_secret.openai_key.id})"
      OPENAI_MODEL           = var.openai_model
      OPENAI_OPTIMIZER_MODEL = var.openai_optimizer_model
      OPENAI_EMBEDDING_MODEL = var.openai_embedding_model

      # Pinecone settings (INDEX_NAME preferred by bot; INDEX kept for legacy / deploy scripts)
      PINECONE_API_KEY    = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault_secret.pinecone_key.id})"
      PINECONE_INDEX      = var.pinecone_index_name
      PINECONE_INDEX_NAME = var.pinecone_index_name
      PINECONE_NAMESPACE  = var.pinecone_namespace

      APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.main.connection_string
    },
    trimspace(var.sharepoint_library_base_url) != "" ? {
      SHAREPOINT_LIBRARY_BASE_URL = trimspace(var.sharepoint_library_base_url)
    } : {},
  )

  identity {
    type = "SystemAssigned"
  }

  tags = local.tags

  lifecycle {
    ignore_changes = [
      # Ignore changes to app settings that might be updated by deployments
      app_settings["WEBSITE_RUN_FROM_PACKAGE"],
    ]
  }
}

# Grant Function App access to Key Vault
resource "azurerm_key_vault_access_policy" "function_app" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_linux_function_app.main.identity[0].principal_id

  secret_permissions = [
    "Get",
    "List",
  ]
}
