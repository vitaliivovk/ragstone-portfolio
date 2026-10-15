#!/usr/bin/env bash
# Knowledge base / Pinecone operations (Docker by default).
#
# Usage (repo root):
#   ./scripts/kb.sh reindex "Topic/file.docx" [--force]
#   ./scripts/kb.sh delete --source-relative-path "Topic/file.docx"
#   ./scripts/kb.sh delete --doc-id "<sha1>"
#   ./scripts/kb.sh index
#   ./scripts/kb.sh qa-export [--seed 42]
#   ./scripts/kb.sh sharepoint --auth device --dry-run
#
# Windows: scripts\kb.cmd reindex "Topic/file.docx"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/docker-pinecone.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/docker-dev.sh"

CMD="${1:?Usage: $0 <reindex|delete|index|qa-export|sharepoint> ...}"
shift

_kb_pinecone_uv() {
    ragstone_docker_pinecone_uv "$PROJECT_ROOT" "run python $*"
}

_kb_pinecone_index() {
    ragstone_docker_pinecone_ensure "$PROJECT_ROOT"
    docker compose -f "$PROJECT_ROOT/docker-compose.pinecone.yml" run --rm \
        -e RAGSTONE_IN_PINECONE=1 \
        pinecone-indexer
}

case "$CMD" in
    sharepoint)
        ragstone_docker_dev_run "$PROJECT_ROOT" "python scripts/sharepoint_sync.py $(printf '%q ' "$@")"
        ;;
    reindex)
        force_args=()
        paths=()
        for arg in "$@"; do
            if [[ "$arg" == "--force" ]]; then
                force_args+=(--force)
            else
                paths+=("$arg")
            fi
        done
        if [[ ${#paths[@]} -eq 0 ]]; then
            echo "ERROR: reindex requires at least one sourceRelativePath" >&2
            exit 1
        fi
        quoted_paths=""
        for path in "${paths[@]}"; do
            quoted_paths+=" $(printf '%q' "$path")"
        done
        _kb_pinecone_uv "scripts/reindex_files.py ${force_args[*]}${quoted_paths}"
        ;;
    delete)
        _kb_pinecone_uv "scripts/delete_corpus_document.py $(printf '%q ' "$@")"
        ;;
    index)
        if [[ $# -gt 0 ]]; then
            echo "ERROR: index takes no extra arguments" >&2
            exit 1
        fi
        _kb_pinecone_index
        ;;
    qa-export)
        _kb_pinecone_uv "scripts/generate_qa_pairs_from_corpus.py $(printf '%q ' "$@")"
        ;;
    -h|--help|help)
        sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
        ;;
    *)
        echo "ERROR: Unknown command: $CMD" >&2
        exit 1
        ;;
esac
