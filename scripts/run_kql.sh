#!/usr/bin/env bash
# Run Kusto (KQL) against Azure — inline string, stdin, or a .kql file path.
#
# Usage:
#   ./scripts/run_kql.sh -q 'traces | where timestamp > ago(1h) | take 5'
#   echo 'traces | take 3' | ./scripts/run_kql.sh
#   ./scripts/run_kql.sh - < myquery.kql
#   ./scripts/run_kql.sh scripts/kql/rent_payment_audit.kql
#
# Backends:
#   app-insights (default) — traces / requests / exceptions (timestamp, message).
#   workspace — AppTraces / AppRequests (TimeGenerated, Message).
#
# Env: AZURE_RESOURCE_GROUP, AZURE_APP_INSIGHTS_NAME, LOG_ANALYTICS_WORKSPACE_NAME,
#      LOG_ANALYTICS_WORKSPACE_ID (optional; resolved via az if unset).

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="app-insights"
OFFSET="7d"
TIMESPAN="P7D"
FORMAT="jsonc"
KQL_INLINE=""
KQL_FILE=""

usage() {
  cat <<'EOF'
Run KQL against Azure (Application Insights or Log Analytics workspace).

Input (pick one):
  -q, --query "KQL..."     Inline Kusto query string.
  -                       Read KQL from stdin (also used when stdin is a pipe and no file/-q).
  <path>.kql              Read from file (repo-relative or absolute).

Usage:
  scripts/run_kql.sh [options] [-q "KQL" | - | path/to/query.kql]

Options:
  -b, --backend app-insights|workspace   default: app-insights
  -o, --output FORMAT                    jsonc, json, table, tsv (default: jsonc)
      --offset OFFSET                    app-insights time window (default: 7d)
  -t, --timespan SPAN                    workspace ISO8601 duration (default: P7D)
  -h, --help                             This help

Examples:
  scripts/run_kql.sh -q 'traces | where timestamp > ago(1d) | take 5'
  echo 'traces | take 3' | scripts/run_kql.sh
  scripts/run_kql.sh scripts/kql/rent_payment_audit.kql
  scripts/run_kql.sh -b workspace -o table scripts/kql/rag_audit_ukrainian_rent.kql
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -b|--backend)
      BACKEND="$2"
      shift 2
      ;;
    -o|--output)
      FORMAT="$2"
      shift 2
      ;;
    --offset)
      OFFSET="$2"
      shift 2
      ;;
    -t|--timespan)
      TIMESPAN="$2"
      shift 2
      ;;
    -q|--query)
      KQL_INLINE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      if [ -n "${KQL_FILE}" ]; then
        echo "Extra argument: $1 (only one path, or use -q)" >&2
        exit 1
      fi
      KQL_FILE="$1"
      shift
      ;;
  esac
done

if [ -n "${KQL_INLINE}" ] && [ -n "${KQL_FILE}" ]; then
  echo "ERROR: use either -q/--query or a file path (or -), not both." >&2
  exit 1
fi

# Drop full-line // comments and blank lines; collapse to one line for az CLI.
normalize_kql_stream() {
  sed -e '/^[[:space:]]*\/\//d' -e '/^[[:space:]]*$/d' | tr '\n' ' ' | tr -s ' ' | sed 's/^ //;s/ $//'
}

QUERY=""
if [ -n "${KQL_INLINE}" ]; then
  QUERY="$(printf '%s\n' "${KQL_INLINE}" | normalize_kql_stream)"
elif [ "${KQL_FILE}" = "-" ]; then
  QUERY="$(normalize_kql_stream)"
elif [ -n "${KQL_FILE}" ]; then
  if [ -f "${ROOT}/${KQL_FILE}" ]; then
    KQL_PATH="${ROOT}/${KQL_FILE}"
  elif [ -f "${KQL_FILE}" ]; then
    KQL_PATH="${KQL_FILE}"
  else
    echo "ERROR: KQL file not found: ${KQL_FILE}" >&2
    exit 1
  fi
  QUERY="$(normalize_kql_stream < "${KQL_PATH}")"
elif [ ! -t 0 ]; then
  QUERY="$(normalize_kql_stream)"
else
  echo "ERROR: pass KQL via -q '...', pipe stdin, or a path to a .kql file." >&2
  usage >&2
  exit 1
fi

if [ -z "${QUERY}" ]; then
  echo "ERROR: KQL query is empty after normalization." >&2
  exit 1
fi

RG="${AZURE_RESOURCE_GROUP:-rg-northwind-dev}"
APP="${AZURE_APP_INSIGHTS_NAME:-appi-northwind-dev}"
WS_NAME="${LOG_ANALYTICS_WORKSPACE_NAME:-log-northwind-dev}"

if ! command -v az >/dev/null 2>&1; then
  echo "ERROR: Azure CLI (az) not found. Run inside dev Docker: docker compose -f docker-compose.dev.yml run --rm -T dev bash /workspace/scripts/run_kql.sh ..." >&2
  exit 1
fi

case "${BACKEND}" in
  app-insights)
    exec az monitor app-insights query \
      --apps "${APP}" \
      --resource-group "${RG}" \
      --offset "${OFFSET}" \
      --analytics-query "${QUERY}" \
      -o "${FORMAT}"
    ;;
  workspace)
    CUSTOMER_ID="${LOG_ANALYTICS_WORKSPACE_ID:-}"
    if [ -z "${CUSTOMER_ID}" ]; then
      CUSTOMER_ID="$(az monitor log-analytics workspace show \
        --resource-group "${RG}" \
        --workspace-name "${WS_NAME}" \
        --query customerId \
        -o tsv 2>/dev/null || true)"
    fi
    if [ -z "${CUSTOMER_ID}" ]; then
      echo "ERROR: Could not resolve Log Analytics customer ID. Set LOG_ANALYTICS_WORKSPACE_ID or ensure workspace '${WS_NAME}' exists in '${RG}'." >&2
      exit 1
    fi
    exec az monitor log-analytics query \
      --workspace "${CUSTOMER_ID}" \
      --timespan "${TIMESPAN}" \
      --analytics-query "${QUERY}" \
      -o "${FORMAT}"
    ;;
  *)
    echo "ERROR: backend must be 'app-insights' or 'workspace', got: ${BACKEND}" >&2
    exit 1
    ;;
esac
