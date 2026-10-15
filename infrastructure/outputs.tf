output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "bot_app_id" {
  description = "Azure AD Application ID for the bot"
  value       = azuread_application.bot.client_id
}

output "bot_name" {
  description = "Azure Bot Service name"
  value       = azurerm_bot_service_azure_bot.main.name
}

output "function_app_name" {
  description = "Azure Functions app name"
  value       = azurerm_linux_function_app.main.name
}

output "function_app_url" {
  description = "Azure Functions app URL"
  value       = "https://${azurerm_linux_function_app.main.default_hostname}"
}

output "bot_endpoint" {
  description = "Bot messaging endpoint URL"
  value       = "https://${azurerm_linux_function_app.main.default_hostname}/api/messages"
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = azurerm_key_vault.main.name
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.main.vault_uri
}

# For Teams App manifest
output "teams_app_config" {
  description = "Configuration for Teams app manifest"
  value = {
    bot_id   = azuread_application.bot.client_id
    endpoint = "https://${azurerm_linux_function_app.main.default_hostname}/api/messages"
  }
}

# Deployment command helper
output "deploy_command" {
  description = "Command to deploy Functions code"
  value       = "func azure functionapp publish ${azurerm_linux_function_app.main.name} --python"
}

output "application_insights_name" {
  description = "Application Insights resource name (Azure Portal → Monitor → Logs)"
  value       = azurerm_application_insights.main.name
}

output "log_analytics_workspace_id" {
  description = "Log Analytics workspace resource ID backing Application Insights"
  value       = azurerm_log_analytics_workspace.main.id
}

# LibreChat / ACA (null when librechat_enabled = false)
output "librechat_enabled" {
  description = "Whether LibreChat ACA resources are managed in this workspace"
  value       = var.librechat_enabled
}

output "librechat_environment_id" {
  description = "Container Apps environment ID (null if LibreChat disabled)"
  value       = try(azurerm_container_app_environment.librechat[0].id, null)
}

output "librechat_fqdn" {
  description = "LibreChat ACA default FQDN (null if disabled). Use for DOMAIN_* or DNS CNAME target."
  value       = try(azurerm_container_app.librechat[0].ingress[0].fqdn, null)
}

output "librechat_url" {
  description = "LibreChat HTTPS URL (custom domain if set, else ACA FQDN)"
  value = var.librechat_enabled ? (
    trimspace(var.librechat_custom_domain) != ""
    ? "https://${trimspace(var.librechat_custom_domain)}"
    : try("https://${azurerm_container_app.librechat[0].ingress[0].fqdn}", null)
  ) : null
}

output "librechat_rag_adapter_base_url" {
  description = "Configured RAG adapter /v1 base URL for LibreChat custom endpoint"
  value       = var.librechat_enabled ? var.librechat_rag_adapter_base_url : null
}

output "librechat_mongo_provider" {
  description = "Selected Mongo hosting mode (none | cosmos_vcore | atlas)"
  value       = var.librechat_mongo_provider
}
