#!/usr/bin/env bash
# Apply PINECONE_* Function App settings from environments/<env>.tfvars via Azure CLI.
# Terraform apply also sets these, but code-only deploy (func publish) does not — without this
# step the app can stay on an old namespace (e.g. v2) while tfvars say v3.
#
# Usage: sync-pinecone-appsettings.sh <dev|prod> <resource_group> <function_app_name>
set -eu

ENV="${1:?Usage: $0 <dev|prod> <resource_group> <function_app_name>}"
RESOURCE_GROUP="${2:?missing resource_group}"
FUNCTION_APP="${3:?missing function_app_name}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TFVARS_FILE="$PROJECT_ROOT/infrastructure/environments/${ENV}.tfvars"

if [[ ! -f "$TFVARS_FILE" ]]; then
  echo "ERROR: $TFVARS_FILE not found"
  exit 1
fi

# Strip CR for Windows line endings; parse HCL-style quoted values
pinecone_line() {
  local key="$1"
  grep -E "^[[:space:]]*${key}[[:space:]]*=" "$TFVARS_FILE" | head -1 | tr -d '\r'
}

line_ns="$(pinecone_line pinecone_namespace)"
line_idx="$(pinecone_line pinecone_index_name)"
if [[ -z "$line_ns" || -z "$line_idx" ]]; then
  echo "ERROR: Could not parse pinecone_namespace / pinecone_index_name from $TFVARS_FILE"
  exit 1
fi

PINECONE_NS="$(echo "$line_ns" | sed -E 's/^[[:space:]]*pinecone_namespace[[:space:]]*=[[:space:]]*\"([^\"]*)\".*$/\1/')"
PINECONE_IDX="$(echo "$line_idx" | sed -E 's/^[[:space:]]*pinecone_index_name[[:space:]]*=[[:space:]]*\"([^\"]*)\".*$/\1/')"

if [[ -z "$PINECONE_NS" || -z "$PINECONE_IDX" ]]; then
  echo "ERROR: Failed to extract Pinecone values from tfvars (expect double-quoted values)"
  exit 1
fi

echo "Syncing Function App Pinecone settings from $TFVARS_FILE"
echo "  PINECONE_NAMESPACE=$PINECONE_NS"
echo "  PINECONE_INDEX / PINECONE_INDEX_NAME=$PINECONE_IDX"

az functionapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FUNCTION_APP" \
  --settings \
  "PINECONE_NAMESPACE=$PINECONE_NS" \
  "PINECONE_INDEX=$PINECONE_IDX" \
  "PINECONE_INDEX_NAME=$PINECONE_IDX" \
  --output none

echo "Pinecone app settings updated."
