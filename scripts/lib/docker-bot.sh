#!/usr/bin/env bash
# Bot-test Docker helpers for bot.sh.

ragstone_in_bot_test() {
    [[ "${RAGSTONE_IN_BOT_TEST:-}" == "1" ]] || [[ "${PWD:-}" == */teams-bot ]]
}

ragstone_docker_bot_ensure() {
    if ! docker info >/dev/null 2>&1; then
        echo "ERROR: Docker is not running. Start Docker Desktop and retry." >&2
        exit 1
    fi
    local root="${1:?}"
    if [[ ! -f "$root/docker-compose.bot.yml" ]]; then
        echo "ERROR: Run from repository root (docker-compose.bot.yml missing)." >&2
        exit 1
    fi
    docker compose -f "$root/docker-compose.bot.yml" build bot-test
}

ragstone_docker_bot_run() {
    local root="${1:?}"
    local inner_cmd="${2:?}"
    ragstone_docker_bot_ensure "$root"
    docker compose -f "$root/docker-compose.bot.yml" run --rm \
        -e RAGSTONE_IN_BOT_TEST=1 \
        bot-test bash -lc "cd /workspace/teams-bot && $inner_cmd"
}
