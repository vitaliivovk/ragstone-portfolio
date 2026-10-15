#!/bin/bash
# Fast deployment script - builds locally and skips remote build
# Usage: ./scripts/deploy-fast.sh [dev|prod]
#
# This is faster than remote build (~30s vs ~2min) but requires:
# - Running from Linux (Docker container)
# - Initial remote build to have been done at least once
#
# Prefer: ./scripts/deploy.sh <dev|prod>  (branch checks + Docker).
# Git: dev → main; prod → release.

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

# Match subscription to Terraform resources (Docker volume may default to another sub).
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
# Dev state lives in workspace "default"; prod in workspace "prod" (see infrastructure/terraform.tfstate.d/).
# Match workspace to ENV so we deploy to the correct Function App.
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

echo "=== Fast Deploy to Azure Functions ($ENV) ==="
echo "Function App: $FUNCTION_APP"
echo "Resource Group: $RESOURCE_GROUP"
echo ""

# Navigate to bot directory
cd "$SCRIPT_DIR/../teams-bot"

# Step 1: Install dependencies locally (only if needed)
PACKAGES_DIR=".python_packages/lib/site-packages"
REQUIREMENTS_HASH=$(md5sum requirements.txt | cut -d' ' -f1)
HASH_FILE=".python_packages/.requirements_hash"

if [ ! -d "$PACKAGES_DIR" ] || [ ! -f "$HASH_FILE" ] || [ "$REQUIREMENTS_HASH" != "$(cat $HASH_FILE 2>/dev/null)" ]; then
    echo "Installing dependencies locally..."
    rm -rf .python_packages
    pip install --target="$PACKAGES_DIR" -r requirements.txt --quiet --platform manylinux2014_x86_64 --only-binary=:all: 2>/dev/null || \
    pip install --target="$PACKAGES_DIR" -r requirements.txt --quiet
    echo "$REQUIREMENTS_HASH" > "$HASH_FILE"
    echo "Dependencies installed."
else
    echo "Dependencies unchanged, skipping install."
fi

# Step 2: Deploy with --no-build (skips remote pip install)
echo "Deploying to $FUNCTION_APP..."
func azure functionapp publish "$FUNCTION_APP" --python --no-build

# Step 3: Align Pinecone app settings with environments/<env>.tfvars (func publish does not update them)
bash "$SCRIPT_DIR/lib/sync-pinecone-appsettings.sh" "$ENV" "$RESOURCE_GROUP" "$FUNCTION_APP"

# Step 4: Force trigger sync (important for --no-build)
echo "Syncing triggers..."
az functionapp restart --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --output none

# Step 5: Wait for cold start
echo "Waiting for function app to start..."
sleep 10

# Step 6: Verify deployment
echo "Verifying deployment..."
HEALTH=$(curl -s "https://${FUNCTION_APP}.azurewebsites.net/api/health" || echo "failed")
if echo "$HEALTH" | grep -q "healthy"; then
    echo "Health check passed!"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
else
    echo "Warning: Health check failed, function may still be starting..."
    echo "Try: curl https://${FUNCTION_APP}.azurewebsites.net/api/health"
fi

echo ""
echo "=== Deployment complete ($ENV) ==="
