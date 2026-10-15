@echo off
REM Bot tests / local RAG / probes via bot-test Docker image.
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: scripts\bot.cmd ^<pytest^|rag^|probe^|run^> ...
  exit /b 1
)
docker compose -f docker-compose.bot.yml build bot-test
if errorlevel 1 exit /b 1
docker compose -f docker-compose.bot.yml run --rm -e RAGSTONE_IN_BOT_TEST=1 bot-test bash -lc "cd /workspace && ./scripts/bot.sh --local %*"
exit /b %ERRORLEVEL%
