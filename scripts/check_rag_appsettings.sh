#!/usr/bin/env bash
# List RAG-related Function App settings (dev or prod).
# Usage: ./scripts/check_rag_appsettings.sh [dev|prod]
set -eu

ENV="${1:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck disable=SC1091
source <(sed 's/\r$//' "$SCRIPT_DIR/lib/dotenv_azure.sh")
if [ -f "$PROJECT_ROOT/.env" ]; then
  SUB="$(ragstone_azure_subscription_for_env "$ENV")"
  if [ -n "$SUB" ]; then
    echo "Azure subscription ($ENV): $SUB"
    az account set --subscription "$SUB"
  fi
fi

az account show --query "{subscription:name, id:id}" -o table

cd "$PROJECT_ROOT/infrastructure"
if [ "$ENV" = "prod" ]; then
  terraform workspace select prod
else
  terraform workspace select default
fi

FUNCTION_APP="$(terraform output -raw function_app_name)"
RESOURCE_GROUP="$(terraform output -raw resource_group_name)"
echo ""
echo "Function App: $FUNCTION_APP"
echo "Resource Group: $RESOURCE_GROUP"
echo ""
echo "=== RAG-related app settings ==="
az functionapp config appsettings list \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FUNCTION_APP" \
  --query "[?starts_with(name, 'RAG_') || name=='MAX_RAG_CONTEXT_CHARS' || name=='SUMMARY_RETRIEVAL_ENABLED'].{name:name, value:value}" \
  -o table

echo ""
echo "=== RAG_HANDBOOK_DIRECT_ENABLED (exact) ==="
HANDBOOK_JSON="$(az functionapp config appsettings list \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FUNCTION_APP" \
  --query "[?name=='RAG_HANDBOOK_DIRECT_ENABLED']" \
  -o json)"
echo "$HANDBOOK_JSON"
if [ "$HANDBOOK_JSON" = "[]" ]; then
  echo "(not set in Azure — bot uses code default from deployed package)"
fi
