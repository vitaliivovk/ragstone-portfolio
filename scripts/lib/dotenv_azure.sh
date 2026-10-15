#!/usr/bin/env bash
# Read Azure tenant/subscription from repo .env for a given environment (dev|prod).
# Requires: PROJECT_ROOT points at repo root and .env exists at PROJECT_ROOT/.env

ragstone_dotenv_get() {
    local key="${1:?}"
    grep -E "^${key}=" "$PROJECT_ROOT/.env" 2>/dev/null | head -1 | cut -d '=' -f2- | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

ragstone_azure_tenant_for_env() {
    local env_name="${1:?}"
    if [ "$env_name" = "prod" ]; then
        ragstone_dotenv_get PROD_AZURE_TENANT_ID
        return
    fi
    local tenant
    tenant=$(ragstone_dotenv_get DEV_AZURE_TENANT_ID)
    if [ -n "$tenant" ]; then
        echo "$tenant"
        return
    fi
    ragstone_dotenv_get AZURE_TENANT_ID
}

ragstone_azure_subscription_for_env() {
    local env_name="${1:?}"
    if [ "$env_name" = "prod" ]; then
        ragstone_dotenv_get PROD_AZURE_SUBSCRIPTION_ID
        return
    fi
    local sub
    sub=$(ragstone_dotenv_get DEV_AZURE_SUBSCRIPTION_ID)
    if [ -n "$sub" ]; then
        echo "$sub"
        return
    fi
    ragstone_dotenv_get AZURE_SUBSCRIPTION_ID
}
