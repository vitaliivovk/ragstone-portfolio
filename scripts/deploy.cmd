@echo off
REM Unified bot deploy via Docker (repo root). Forwards to deploy.sh inside container.
REM   scripts\deploy.cmd dev
REM   scripts\deploy.cmd dev --terraform
REM   scripts\deploy.cmd dev --full
REM   scripts\deploy.cmd prod --terraform
setlocal
cd /d "%~dp0.."

if not exist "docker-compose.dev.yml" (
  echo ERROR: Run from repository root ^(docker-compose.dev.yml missing^).
  exit /b 1
)

if "%~1"=="" (
  echo Usage: scripts\deploy.cmd ^<dev^|prod^> [--full] [--terraform]
  exit /b 1
)

docker compose -f docker-compose.dev.yml build dev
if errorlevel 1 exit /b 1

docker compose -f docker-compose.dev.yml run --rm -e RAGSTONE_IN_DOCKER=1 dev bash -lc "cd /workspace && ./scripts/deploy.sh --local %*"
exit /b %ERRORLEVEL%
