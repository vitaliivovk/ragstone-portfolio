@echo off
REM KQL via dev Docker image. Forwards to kql.sh / run_kql.sh.
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: scripts\kql.cmd scripts\kql\last_rag_turn.kql
  exit /b 1
)
docker compose -f docker-compose.dev.yml build dev
if errorlevel 1 exit /b 1
docker compose -f docker-compose.dev.yml run --rm -T -e RAGSTONE_IN_DOCKER=1 dev bash /workspace/scripts/run_kql.sh %*
exit /b %ERRORLEVEL%
