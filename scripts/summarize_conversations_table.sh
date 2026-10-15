#!/usr/bin/env bash
# Row counts per user (PartitionKey) in Azure Table conversations.
# docker compose -f docker-compose.dev.yml run --rm -T dev bash /workspace/scripts/summarize_conversations_table.sh
set -eu
CS="${AZURE_STORAGE_CONNECTION_STRING:-}"
if [[ -z "${CS}" ]]; then
  CS="${AzureWebJobsStorage:-}"
fi
if [[ -z "${CS}" ]]; then
  echo "ERROR: Set AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage in repo .env" >&2
  exit 1
fi
JSON="$(az storage entity query --connection-string "${CS}" --table-name conversations -o json)"
total_rows="$(echo "${JSON}" | jq '.items | length')"
unique_users="$(echo "${JSON}" | jq '[.items[].PartitionKey] | unique | length')"
echo "rows	user_id (Teams PartitionKey)"
echo "${JSON}" | jq -r '
  .items
  | group_by(.PartitionKey)
  | map({user: .[0].PartitionKey, rows: length})
  | sort_by(-.rows)
  | .[]
  | "\(.rows)\t\(.user)"
'
echo "---"
echo "distinct_users	${unique_users}"
echo "total_rows	${total_rows}"
