@echo off
REM Terraform via dev Docker image (repo root). Same as: bash scripts/terraform.sh %*
REM   scripts\terraform.cmd dev plan
REM   scripts\terraform.cmd dev apply -auto-approve
setlocal
cd /d "%~dp0.."

if not exist "docker-compose.dev.yml" (
  echo ERROR: Run from repository root.
  exit /b 1
)

docker compose -f docker-compose.dev.yml build dev
if errorlevel 1 exit /b 1

docker compose -f docker-compose.dev.yml run --rm -e RAGSTONE_IN_DOCKER=1 dev bash -lc "cd /workspace && ./scripts/terraform.sh --local %*"
exit /b %ERRORLEVEL%
