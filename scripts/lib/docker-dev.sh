#!/usr/bin/env bash
# Shared dev Docker image helpers for terraform.sh and deploy.sh.

ragstone_in_docker() {
    [[ -f /.dockerenv ]] || [[ "${RAGSTONE_IN_DOCKER:-}" == "1" ]]
}

ragstone_repo_root_from_script() {
    local script_dir="${1:?}"
    cd "$script_dir/.." && pwd
}

ragstone_docker_dev_ensure() {
    if ! docker info >/dev/null 2>&1; then
        echo "ERROR: Docker is not running. Start Docker Desktop and retry." >&2
        exit 1
    fi
    local root="${1:?}"
    if [[ ! -f "$root/docker-compose.dev.yml" ]]; then
        echo "ERROR: Run from repository root (docker-compose.dev.yml missing)." >&2
        exit 1
    fi
    docker compose -f "$root/docker-compose.dev.yml" build dev
}

ragstone_docker_dev_run() {
    local root="${1:?}"
    local inner_cmd="${2:?}"
    ragstone_docker_dev_ensure "$root"
    docker compose -f "$root/docker-compose.dev.yml" run --rm \
        -e RAGSTONE_IN_DOCKER=1 \
        dev bash -lc "cd /workspace && $inner_cmd"
}
