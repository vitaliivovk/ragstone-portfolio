#!/usr/bin/env bash
# Pinecone indexer Docker helpers for kb.sh.

ragstone_in_pinecone_indexer() {
    [[ "${RAGSTONE_IN_PINECONE:-}" == "1" ]] || [[ -d /data/docs && -d /data/chunk_output ]]
}

ragstone_docker_pinecone_ensure() {
    if ! docker info >/dev/null 2>&1; then
        echo "ERROR: Docker is not running. Start Docker Desktop and retry." >&2
        exit 1
    fi
    local root="${1:?}"
    if [[ ! -f "$root/docker-compose.pinecone.yml" ]]; then
        echo "ERROR: Run from repository root (docker-compose.pinecone.yml missing)." >&2
        exit 1
    fi
    docker compose -f "$root/docker-compose.pinecone.yml" build pinecone-indexer
}

ragstone_docker_pinecone_run() {
    local root="${1:?}"
    local inner_cmd="${2:?}"
    ragstone_docker_pinecone_ensure "$root"
    docker compose -f "$root/docker-compose.pinecone.yml" run --rm \
        -e RAGSTONE_IN_PINECONE=1 \
        pinecone-indexer bash -lc "$inner_cmd"
}

ragstone_docker_pinecone_uv() {
    local root="${1:?}"
    local inner_cmd="${2:?}"
    ragstone_docker_pinecone_ensure "$root"
    docker compose -f "$root/docker-compose.pinecone.yml" run --rm \
        -e RAGSTONE_IN_PINECONE=1 \
        --entrypoint uv \
        pinecone-indexer bash -lc "$inner_cmd"
}
