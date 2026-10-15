#!/usr/bin/env bash
# Run clear_conversation_memory.py inside the ragstone dev container (Azure CLI + Python image).
# Uses AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage from repo .env (compose interpolation).
#
# From repo root:
#   docker compose -f docker-compose.dev.yml run --rm -T dev bash /workspace/scripts/clear_conversation_memory_docker.sh --all --yes
#   docker compose -f docker-compose.dev.yml run --rm -T dev bash /workspace/scripts/clear_conversation_memory_docker.sh --user-id '29:1...' --yes
set -eu
cd /workspace/teams-bot
python3 -m pip install -q -r requirements.txt
exec python3 scripts/clear_conversation_memory.py "$@"
