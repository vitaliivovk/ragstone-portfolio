# Storage Account for Azure Functions
resource "azurerm_storage_account" "functions" {
  name                     = "st${replace(local.base_name, "-", "")}${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  min_tls_version = "TLS1_2"

  tags = local.tags
}
