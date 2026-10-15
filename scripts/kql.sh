#!/usr/bin/env bash
# App Insights / Log Analytics KQL (dev Docker image by default).
#
# Usage (repo root):
#   ./scripts/kql.sh scripts/kql/last_rag_turn.kql
#   ./scripts/kql.sh -q 'traces | take 5'
#   ./scripts/kql.sh -b workspace -t P2D -o table scripts/kql/dev_recent_turns_and_stops.kql
#
# Windows: scripts\kql.cmd scripts\kql\last_rag_turn.kql
#
# Full options: scripts/run_kql.sh --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/docker-dev.sh"

if ragstone_in_docker; then
    exec "$SCRIPT_DIR/run_kql.sh" "$@"
fi

ragstone_docker_dev_run "$PROJECT_ROOT" "./scripts/run_kql.sh $(printf '%q ' "$@")"
