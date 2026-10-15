#!/bin/bash
# Full deployment script - uses Azure remote build
# Usage: ./scripts/deploy-full.sh [dev|prod]
#
# This is slower (~2min) but more reliable:
# - Builds dependencies on Azure (correct platform)
# - Automatically syncs triggers
# - Use this for first deployment or when --no-build fails
#
# Prefer: ./scripts/deploy.sh <dev|prod> [--full]

set -e

ENV="${1:-dev}"

# Validate environment
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "ERROR: Environment must be 'dev' or 'prod'"
    echo "Usage: $0 [dev|prod]"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PROJECT_ROOT
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/git-deploy-branch.sh"
ragstone_require_deploy_branch "$ENV"

# shellcheck disable=SC1091
source <(sed 's/\r$//' "$SCRIPT_DIR/lib/dotenv_azure.sh")
if [ -f "$PROJECT_ROOT/.env" ]; then
    AZURE_SUBSCRIPTION_ID=$(ragstone_azure_subscription_for_env "$ENV")
    if [ -n "$AZURE_SUBSCRIPTION_ID" ]; then
        echo "Selecting Azure subscription from .env ($ENV: PROD_* / DEV_* or legacy AZURE_*)..."
        az account set --subscription "$AZURE_SUBSCRIPTION_ID"
    fi
fi

# Navigate to infrastructure directory to get terraform outputs.
# Dev state: workspace "default"; prod: workspace "prod".
cd "$SCRIPT_DIR/../infrastructure"

if [ "$ENV" = "prod" ]; then
    if ! terraform workspace select prod 2>/dev/null; then
        echo "ERROR: Terraform workspace 'prod' not found."
        echo "From infrastructure/: run ./scripts/terraform.sh prod init && ./scripts/terraform.sh prod apply"
        exit 1
    fi
else
    terraform workspace select default
fi

FUNCTION_APP=$(terraform output -raw function_app_name 2>/dev/null) || {
    echo "ERROR: Could not get function_app_name from terraform output"
    echo "Initialize and apply infrastructure first:"
    echo "  ./scripts/terraform.sh $ENV init"
    echo "  ./scripts/terraform.sh $ENV apply"
    exit 1
}
RESOURCE_GROUP=$(terraform output -raw resource_group_name 2>/dev/null)

echo "=== Full Deploy to Azure Functions ($ENV, remote build) ==="
echo "Function App: $FUNCTION_APP"
echo "Resource Group: $RESOURCE_GROUP"
echo ""

# Navigate to bot directory
cd "$SCRIPT_DIR/../teams-bot"

# Clean up any local packages (remote build handles dependencies)
rm -rf .python_packages

# Deploy with remote build
echo "Deploying to $FUNCTION_APP..."
func azure functionapp publish "$FUNCTION_APP" --python

bash "$SCRIPT_DIR/lib/sync-pinecone-appsettings.sh" "$ENV" "$RESOURCE_GROUP" "$FUNCTION_APP"

echo ""
echo "=== Deployment complete ($ENV) ==="
