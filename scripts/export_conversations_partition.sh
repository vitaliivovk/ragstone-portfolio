#!/usr/bin/env bash
# Export all table rows for one PartitionKey to a text file (JSON + human-readable).
# Usage: bash /workspace/scripts/export_conversations_partition.sh '<PartitionKey>' [out_path]
# Example: docker compose -f docker-compose.dev.yml run --rm -T dev bash /workspace/scripts/export_conversations_partition.sh '29:1LM...'
set -eu
PART="${1:?PartitionKey required}"
OUT="${2:-/workspace/conversation_exports/conversation_memory_export.txt}"
CS="${AZURE_STORAGE_CONNECTION_STRING:-}"
if [[ -z "${CS}" ]]; then
  CS="${AzureWebJobsStorage:-}"
fi
if [[ -z "${CS}" ]]; then
  echo "ERROR: Set AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage in repo .env" >&2
  exit 1
fi
FILTER="PartitionKey eq '${PART//\'/\'\'}'"
JSON="$(az storage entity query --connection-string "${CS}" --table-name conversations --filter "${FILTER}" -o json)"
mkdir -p "$(dirname "${OUT}")"
{
  echo "=== conversation memory export ==="
  echo "PartitionKey: ${PART}"
  echo "generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "row_count: $(echo "${JSON}" | jq '.items | length')"
  echo ""
  echo "=== JSON (full entities) ==="
  echo "${JSON}" | jq .
  echo ""
  echo "=== chronological (Timestamp) ==="
  echo "${JSON}" | jq -r '
    .items
    | sort_by(.Timestamp)
    | .[]
    | "[\(.Role // .role // "?") | \(.Timestamp // "?")]\n\(.Content // .content // "")\n"
  '
} > "${OUT}"
echo "Wrote ${OUT}"
