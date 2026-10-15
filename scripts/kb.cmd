@echo off
REM Knowledge base / Pinecone via Docker (repo root).
REM   scripts\kb.cmd reindex "Topic\file.docx" [--force]
REM   scripts\kb.cmd delete --source-relative-path "Topic\file.docx"
REM   scripts\kb.cmd index
REM   scripts\kb.cmd qa-export --seed 42
REM   scripts\kb.cmd sharepoint --auth device --dry-run
setlocal
cd /d "%~dp0.."

if "%~1"=="" (
  echo Usage: scripts\kb.cmd ^<reindex^|delete^|index^|qa-export^|sharepoint^> ...
  exit /b 1
)

if /i "%~1"=="sharepoint" (
  docker compose -f docker-compose.dev.yml build dev
  if errorlevel 1 exit /b 1
  docker compose -f docker-compose.dev.yml run --rm dev bash -lc "cd /workspace && python scripts/sharepoint_sync.py %2 %3 %4 %5 %6 %7 %8 %9"
  exit /b %ERRORLEVEL%
)

docker compose -f docker-compose.pinecone.yml build pinecone-indexer
if errorlevel 1 exit /b 1

if /i "%~1"=="index" (
  docker compose -f docker-compose.pinecone.yml run --rm pinecone-indexer
  exit /b %ERRORLEVEL%
)

if /i "%~1"=="qa-export" (
  docker compose -f docker-compose.pinecone.yml run --rm --entrypoint uv pinecone-indexer run python scripts/generate_qa_pairs_from_corpus.py %2 %3 %4 %5 %6 %7 %8 %9
  exit /b %ERRORLEVEL%
)

if /i "%~1"=="delete" (
  docker compose -f docker-compose.pinecone.yml run --rm --entrypoint uv pinecone-indexer run python scripts/delete_corpus_document.py %2 %3 %4 %5 %6 %7 %8 %9
  exit /b %ERRORLEVEL%
)

if /i "%~1"=="reindex" (
  docker compose -f docker-compose.pinecone.yml run --rm --entrypoint uv pinecone-indexer run python scripts/reindex_files.py %2 %3 %4 %5 %6 %7 %8 %9
  exit /b %ERRORLEVEL%
)

echo ERROR: Unknown command %1
exit /b 1
