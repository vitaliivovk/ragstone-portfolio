#!/usr/bin/env bash
# Bot evaluation runtime (Docker bot-test image by default).
#
# Usage (repo root):
#   ./scripts/bot.sh pytest [pytest args...]
#   ./scripts/bot.sh rag --question "…"
#   ./scripts/bot.sh rag --file logs/client_feedback_golden.txt
#   ./scripts/bot.sh probe "pytanie" --top-k 8
#   ./scripts/bot.sh run func start
#
# Windows: scripts\bot.cmd pytest tests/ -q

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/docker-bot.sh"

LOCAL=0
ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "--local" ]]; then
        LOCAL=1
    else
        ARGS+=("$arg")
    fi
done

CMD="${ARGS[0]:?Usage: $0 <pytest|rag|probe|run> ...}"
shift_args=("${ARGS[@]:1}")

if [[ $LOCAL -eq 0 ]] && ! ragstone_in_bot_test; then
    quoted_args=""
    for arg in "${ARGS[@]}"; do
        quoted_args+=" $(printf '%q' "$arg")"
    done
    inner="./scripts/bot.sh --local${quoted_args}"
    echo "RAGStone:${inner} (via bot-test Docker)..."
    ragstone_docker_bot_run "$PROJECT_ROOT" "$inner"
    exit $?
fi

cd "$PROJECT_ROOT/teams-bot"

case "$CMD" in
    pytest)
        exec pytest "${shift_args[@]}"
        ;;
    rag)
        exec python scripts/run_local_rag_tests.py "${shift_args[@]}"
        ;;
    probe)
        exec python scripts/probe_pinecone_retrieval.py "${shift_args[@]}"
        ;;
    run)
        exec "${shift_args[@]}"
        ;;
    -h|--help|help)
        sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
        ;;
    *)
        echo "ERROR: Unknown command: $CMD (use pytest|rag|probe|run)" >&2
        exit 1
        ;;
esac
