# Azure AD Application for Bot
resource "azuread_application" "bot" {
  display_name     = "Northwind Assistant Bot (${var.environment})"
  sign_in_audience = "AzureADMyOrg" # Single tenant

  api {
    requested_access_token_version = 2
  }

  web {
    implicit_grant {
      access_token_issuance_enabled = false
      id_token_issuance_enabled     = false
    }
  }

  tags = ["Bot", var.environment]
}

# Service Principal for the Bot App
resource "azuread_service_principal" "bot" {
  client_id                    = azuread_application.bot.client_id
  app_role_assignment_required = false
}

# Client Secret for Bot Authentication
resource "azuread_application_password" "bot" {
  application_id = azuread_application.bot.id
  display_name   = "Terraform managed - ${var.environment}"
  end_date       = timeadd(timestamp(), "8760h") # 1 year

  lifecycle {
    ignore_changes = [end_date]
  }
}

# Azure Bot Service
resource "azurerm_bot_service_azure_bot" "main" {
  name                    = "bot-${local.base_name}-${random_string.suffix.result}"
  resource_group_name     = azurerm_resource_group.main.name
  location                = "global"
  sku                     = var.environment == "prod" ? "S1" : "F0"
  microsoft_app_id        = azuread_application.bot.client_id
  microsoft_app_tenant_id = data.azurerm_client_config.current.tenant_id

  # Endpoint will be set after Functions deployment
  endpoint = "https://${azurerm_linux_function_app.main.default_hostname}/api/messages"

  microsoft_app_type           = "SingleTenant"
  local_authentication_enabled = true

  tags = local.tags
}

# Teams Channel
resource "azurerm_bot_channel_ms_teams" "main" {
  bot_name            = azurerm_bot_service_azure_bot.main.name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_bot_service_azure_bot.main.location

  deployment_environment = "CommercialDeployment"
}
