#!/usr/bin/env bash
# Run inside the dev Docker image (has Azure CLI). Writes under /workspace/logs (host: ./logs).
set -u

OUT_DIR="${AZURE_LOG_OUT_DIR:-/workspace/logs}"
mkdir -p "$OUT_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$OUT_DIR/azure-fetch-${STAMP}.log"

RG="${AZURE_RESOURCE_GROUP:-rg-northwind-dev}"
APP_INSIGHTS="${AZURE_APP_INSIGHTS_NAME:-appi-northwind-dev}"
FUNC_NAME="${AZURE_FUNCTION_APP_NAME:-func-northwind-dev-xxxxx}"

{
  echo "=== Azure log snapshot ${STAMP} (UTC) ==="
  echo "Resource group: ${RG}"
  echo "Application Insights: ${APP_INSIGHTS}"
  echo "Function app (metadata): ${FUNC_NAME}"
  echo ""

  if ! command -v az >/dev/null; then
    echo "ERROR: Azure CLI not found in container."
    exit 1
  fi

  echo "=== az account show ==="
  az account show -o table 2>&1 || echo "(not logged in or no subscription)"
  echo ""

  echo "=== Application Insights queries (offset 24h) ==="
  set +e
  az monitor app-insights query \
    --apps "$APP_INSIGHTS" \
    --resource-group "$RG" \
    --offset 24h \
    --analytics-query 'traces | where message startswith "RAG_TURN_AUDIT" | order by timestamp desc | take 50' \
    -o json 2>&1
  echo ""
  az monitor app-insights query \
    --apps "$APP_INSIGHTS" \
    --resource-group "$RG" \
    --offset 24h \
    --analytics-query 'exceptions | order by timestamp desc | take 30' \
    -o json 2>&1
  echo ""
  az monitor app-insights query \
    --apps "$APP_INSIGHTS" \
    --resource-group "$RG" \
    --offset 24h \
    --analytics-query 'traces | order by timestamp desc | take 40' \
    -o json 2>&1
  set -e

  echo ""
  echo "=== Function App log config (metadata) ==="
  set +e
  az webapp log show --name "$FUNC_NAME" --resource-group "$RG" -o json 2>&1
  set -e
} | tee "$OUT"

echo ""
echo "Wrote: $OUT"
