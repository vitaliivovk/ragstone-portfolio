#!/usr/bin/env bash
set -e
QUERY_FILE="${1:?usage: run_query.sh <kql-file> [offset]}"
OFFSET="${2:-2h}"
Q=$(tr -d '\r\n' < "$QUERY_FILE")
az monitor app-insights query \
  --apps "${AZURE_APP_INSIGHTS_NAME:-appi-northwind-dev}" \
  --resource-group "${AZURE_RESOURCE_GROUP:-rg-northwind-dev}" \
  --offset "$OFFSET" \
  --analytics-query "$Q" \
  -o json
