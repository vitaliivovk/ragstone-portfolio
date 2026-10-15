#!/usr/bin/env bash
# Run inside ragstone dev container: docker compose -f docker-compose.dev.yml run --rm dev bash /workspace/scripts/query_conversations_table.sh
set -eu
CS="${AZURE_STORAGE_CONNECTION_STRING:-}"
if [[ -z "${CS}" ]]; then
  CS="${AzureWebJobsStorage:-}"
fi
if [[ -z "${CS}" ]]; then
  echo "ERROR: Set AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage (e.g. in repo .env for compose interpolation)." >&2
  exit 1
fi
exec az storage entity query --connection-string "${CS}" --table-name conversations -o table "$@"
