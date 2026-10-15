#!/bin/bash
# Terraform wrapper with environment selection and branch protection.
# From repo root on the host, runs inside the dev Docker image automatically.
# Inside the container (or with --local), runs terraform directly.
#
# Usage:
#   ./scripts/terraform.sh <dev|prod> <terraform-command> [args...]
#   ./scripts/terraform.sh --local <dev|prod> <command> [args...]   # skip Docker wrap
#   scripts\terraform.cmd dev plan                                    # Windows
#
# Git sync: dev → branch main; prod → branch release (see deployment-ops skill).
#
# API Keys:
#   Automatically loads OPENAI_API_KEY and PINECONE_API_KEY from .env file.
# Azure identity (from .env, by environment prefix):
#   Dev: DEV_AZURE_TENANT_ID / DEV_AZURE_SUBSCRIPTION_ID, or legacy AZURE_* for dev only.
#   Prod: PROD_AZURE_TENANT_ID / PROD_AZURE_SUBSCRIPTION_ID.
#   These export TF_VAR_tenant_id / TF_VAR_subscription_id. The committed tfvars do not
#   contain tenant/subscription IDs, so one of .env or pre-exported TF_VAR_* is required.
#
# State Management:
#   Dev uses Terraform workspace "default"; prod uses workspace "prod" (separate state under terraform.tfstate.d/).
#   Deploy scripts select the workspace to match ENV before reading outputs.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PROJECT_ROOT

# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/docker-dev.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/git-deploy-branch.sh"

LOCAL=0
if [ "${1:-}" = "--local" ]; then
    LOCAL=1
    shift
fi

ENV="${1:?Usage: $0 [--local] <dev|prod> <command> [args...]}"
shift
CMD="${1:?Usage: $0 [--local] <dev|prod> <command> [args...]}"
shift

if [ "$LOCAL" -eq 0 ] && ! ragstone_in_docker; then
    ragstone_docker_dev_run "$PROJECT_ROOT" "./scripts/terraform.sh --local $ENV $CMD $(printf '%q ' "$@")"
    exit $?
fi

# Navigate to project root and load .env for API keys
# shellcheck disable=SC1091
source <(sed 's/\r$//' "$SCRIPT_DIR/lib/dotenv_azure.sh")

# Validate environment before reading prefixed Azure vars
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "ERROR: Environment must be 'dev' or 'prod'"
    exit 1
fi

if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Loading configuration from .env..."
    
    # API keys
    export TF_VAR_openai_api_key=$(grep -E "^OPENAI_API_KEY=" "$PROJECT_ROOT/.env" | cut -d '=' -f2-)
    export TF_VAR_pinecone_api_key=$(grep -E "^PINECONE_API_KEY=" "$PROJECT_ROOT/.env" | cut -d '=' -f2-)
    
    # Azure tenant/subscription: DEV_* / PROD_* (legacy AZURE_* = dev fallback)
    AZURE_TENANT_ID=$(ragstone_azure_tenant_for_env "$ENV")
    AZURE_SUBSCRIPTION_ID=$(ragstone_azure_subscription_for_env "$ENV")
    
    if [ -n "$AZURE_TENANT_ID" ]; then
        export TF_VAR_tenant_id="$AZURE_TENANT_ID"
    fi
    if [ -n "$AZURE_SUBSCRIPTION_ID" ]; then
        export TF_VAR_subscription_id="$AZURE_SUBSCRIPTION_ID"
    fi
    
    if [ -z "$TF_VAR_openai_api_key" ] || [ -z "$TF_VAR_pinecone_api_key" ]; then
        echo "WARNING: Could not load API keys from .env"
        echo "Make sure OPENAI_API_KEY and PINECONE_API_KEY are set in .env"
    fi
else
    echo "WARNING: .env file not found at $PROJECT_ROOT/.env"
    echo "Set variables in .env or via TF_VAR_ prefix"
fi

ragstone_require_deploy_branch "$ENV"

# Navigate to infrastructure directory
cd "$PROJECT_ROOT/infrastructure"

# Check if tfvars file exists (needed for plan/apply and similar)
TFVARS_FILE="environments/${ENV}.tfvars"
if [ ! -f "$TFVARS_FILE" ]; then
    echo "ERROR: $TFVARS_FILE not found"
    echo "Create it from the template and fill in your tenant/subscription IDs"
    exit 1
fi

# Match workspace to environment (same as deploy-fast.sh)
if [ "$ENV" = "prod" ]; then
    if ! terraform workspace select prod 2>/dev/null; then
        echo "ERROR: Terraform workspace 'prod' not found."
        echo "From infrastructure/: terraform workspace new prod"
        exit 1
    fi
else
    terraform workspace select default
fi

# Only these subcommands accept -var-file; init/fmt/output/workspace/etc. do not.
echo "Environment: $ENV"
case "$CMD" in
    plan|apply|destroy|refresh|import)
        if [ -z "${TF_VAR_tenant_id:-}" ] || [ -z "${TF_VAR_subscription_id:-}" ]; then
            echo "ERROR: TF_VAR_tenant_id / TF_VAR_subscription_id not set"
            echo "Set ${ENV^^}_AZURE_TENANT_ID / ${ENV^^}_AZURE_SUBSCRIPTION_ID in .env or export TF_VAR_* directly"
            exit 1
        fi
        echo "Running: terraform $CMD -var-file=$TFVARS_FILE $*"
        echo ""
        terraform "$CMD" -var-file="$TFVARS_FILE" "$@"
        ;;
    *)
        echo "Running: terraform $CMD $*"
        echo ""
        terraform "$CMD" "$@"
        ;;
esac
