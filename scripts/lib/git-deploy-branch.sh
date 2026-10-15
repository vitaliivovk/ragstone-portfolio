#!/usr/bin/env bash
# Git branch gates: dev deploys track main; prod deploys track release.

ragstone_require_deploy_branch() {
    local env_name="${1:?}"

    if ! command -v git >/dev/null 2>&1; then
        echo "WARNING: git not in PATH — skipping branch check (container scripts may still fail later)."
        return 0
    fi

    local branch
    branch=$(git -C "${PROJECT_ROOT:-.}" rev-parse --abbrev-ref HEAD 2>/dev/null) || {
        echo "WARNING: not a git repository — skipping branch check."
        return 0
    }

    if [ "$env_name" = "prod" ]; then
        if [ "$branch" != "release" ]; then
            echo "=============================================="
            echo "ERROR: Production deploy only from 'release' branch"
            echo "=============================================="
            echo ""
            echo "Current branch: $branch"
            echo ""
            echo "Git + deploy sync:"
            echo "  1. Merge feature work to main and push origin main"
            echo "  2. git fetch origin"
            echo "  3. git checkout release"
            echo "  4. git merge main"
            echo "  5. git push origin release"
            echo "  6. ./scripts/deploy.sh prod  (and append docs/deployments/CHANGELOG.md)"
            echo ""
            exit 1
        fi
        echo "Branch check passed: on 'release' (prod matches release branch)"
        return 0
    fi

    if [ "$env_name" = "dev" ]; then
        if [ "$branch" != "main" ]; then
            echo "=============================================="
            echo "ERROR: Dev deploy only from 'main' branch"
            echo "=============================================="
            echo ""
            echo "Current branch: $branch"
            echo ""
            echo "Git + deploy sync:"
            echo "  1. Merge your feature branch into main (PR or local merge)"
            echo "  2. git push origin main"
            echo "  3. git checkout main && git pull origin main"
            echo "  4. ./scripts/deploy.sh dev"
            echo ""
            exit 1
        fi
        echo "Branch check passed: on 'main' (dev matches main branch)"
    fi
}
