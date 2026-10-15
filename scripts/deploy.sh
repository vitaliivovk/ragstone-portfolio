#!/usr/bin/env bash
# Unified bot deploy (Docker by default). Replaces deploy-*-docker* wrappers.
#
# Usage (repo root):
#   ./scripts/deploy.sh dev                 # deploy-fast on main
#   ./scripts/deploy.sh dev --full          # deploy-full (first deploy / deps)
#   ./scripts/deploy.sh dev --terraform     # terraform init+apply, then deploy-fast
#   ./scripts/deploy.sh prod --terraform    # on release only
#   ./scripts/deploy.sh dev --local         # already inside dev container
#
# Windows (no ExecutionPolicy): scripts\deploy.cmd dev [--full] [--terraform]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PROJECT_ROOT
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/docker-dev.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/git-deploy-branch.sh"

LOCAL=0
TERRAFORM=0
FULL=0
ENV=""

for arg in "$@"; do
    case "$arg" in
        --local) LOCAL=1 ;;
        --terraform) TERRAFORM=1 ;;
        --full) FULL=1 ;;
        -h|--help)
            sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        dev|prod) ENV="$arg" ;;
        *)
            echo "ERROR: Unknown argument: $arg" >&2
            echo "Usage: $0 <dev|prod> [--full] [--terraform] [--local]" >&2
            exit 1
            ;;
    esac
done

ENV="${ENV:?Usage: $0 <dev|prod> [--full] [--terraform] [--local]}"

if [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
    echo "ERROR: Environment must be 'dev' or 'prod'" >&2
    exit 1
fi

if [[ $LOCAL -eq 0 ]] && ! ragstone_in_docker; then
    inner="./scripts/deploy.sh --local"
    [[ $TERRAFORM -eq 1 ]] && inner="$inner --terraform"
    [[ $FULL -eq 1 ]] && inner="$inner --full"
    inner="$inner $ENV"
    echo "RAGStone: $inner (via Docker)..."
    ragstone_docker_dev_run "$PROJECT_ROOT" "$inner"
    exit $?
fi

ragstone_require_deploy_branch "$ENV"

if [[ $TERRAFORM -eq 1 ]]; then
    echo "=== Terraform init + apply ($ENV) ==="
    "$SCRIPT_DIR/terraform.sh" --local "$ENV" init
    "$SCRIPT_DIR/terraform.sh" --local "$ENV" apply -auto-approve
fi

if [[ $FULL -eq 1 ]]; then
    bash "$SCRIPT_DIR/deploy-full.sh" "$ENV"
else
    bash "$SCRIPT_DIR/deploy-fast.sh" "$ENV"
fi
