# RAGStone Pinecone Pipeline

Document processing pipeline that parses, chunks, and indexes documents into Pinecone.

**Extended docs:** [`docs/README.md`](docs/README.md) (corpus remediation, vector DB comparison).

## Features

- **Multi-format parsing**: PDF, DOCX, XLSX, PPTX, and KEY (macOS)
- **Chunking**: ~300 tokens, overlap, section-aware, tables as HTML
- **Dual namespaces**: same vectors upserted to `PINECONE_NAMESPACE_DEV` and `PINECONE_NAMESPACE_PROD` (or legacy `PINECONE_NAMESPACES`)
- **Citation metadata**: `sourceRelativePath` (mirror SharePoint library layout), `sectionPath`, page/slide/sheet, `blockStartIndex` / `blockEndIndex`, `highlightPhrase`, optional `sharepointUrl`
- **JSONL cache**: skip re-parse when cache is newer than source
- **Summary routing vectors** (optional): same namespace as chunks; metadata `summaries=true`, span bounds `chunkIndexStart`/`chunkIndexEnd`; bot queries them first when `SUMMARY_RETRIEVAL_ENABLED=1` (see [`../teams-bot/README.md`](../teams-bot/README.md))

## Corpus layout (`source_data/`)

Default `DOCS_DIR` is `pinecone-pipeline/source_data/`. Unzip `Dokumenty_AI.zip` into that folder. If the zip contains a single top-level folder (e.g. `Dokumenty_AI/`), move its contents up into `source_data/` so supported files are not one extra level deep.

On Windows, if PowerShell `Expand-Archive` fails on long paths, extract with Python (long-path prefix) from `pinecone-pipeline/`:

```python
import os, zipfile
dest = os.path.abspath("source_data")
dest_long = ("\\\\?\\" + dest) if os.name == "nt" else dest
os.makedirs(dest_long, exist_ok=True)
with zipfile.ZipFile(os.path.join("..", "Dokumenty_AI.zip"), "r") as zf:
    zf.extractall(dest_long)
```

Then hoist the inner `Dokumenty_AI` folder if present.

**SharePoint parity:** folder structure under `source_data/` should match the target document library so `sourceRelativePath` maps 1:1 to files in SharePoint. At query time the bot joins the Function App’s **`SHAREPOINT_LIBRARY_BASE_URL`** (from Terraform `sharepoint_library_base_url`) with `sourceRelativePath`, or uses per-vector **`sharepointUrl`** if you set **`SHAREPOINT_BASE_URL`** here at index time. Full flow: [`../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md`](../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md).

After replacing the corpus or changing parsers, clear stale caches once:

```powershell
Remove-Item pinecone-pipeline\chunk_output\*.jsonl
Remove-Item pinecone-pipeline\chunk_output\*.embeddings.jsonl -ErrorAction SilentlyContinue
```

## Installation (local)

```bash
cd pinecone-pipeline
uv sync
```

Configure the repo root `.env` (see [`../.env.example`](../.env.example)).

## Usage (local)

```bash
uv run ragstone-index
# or
python cli.py
```

## Usage (Docker)

From the **repository root**:

```bash
docker compose -f docker-compose.pinecone.yml build
docker compose -f docker-compose.pinecone.yml run --rm pinecone-indexer
```

Mount or extract documents into `pinecone-pipeline/source_data/` before running. The compose file sets `DOCS_DIR=/data/docs` and mounts that directory read-only.

Override env with `-e` or extend `docker-compose.pinecone.yml` as needed. For a standalone image build:

```bash
docker build -t ragstone-pinecone ./pinecone-pipeline
docker run --rm --env-file .env -v ./pinecone-pipeline/source_data:/data/docs:ro \
  -e DOCS_DIR=/data/docs -e SEND_TO_PINECONE=1 ragstone-pinecone
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DOCS_DIR` | Source documents | `pinecone-pipeline/source_data/` |
| `CHUNK_OUTPUT_DIR` | JSONL cache | `pinecone-pipeline/chunk_output/` |
| `SEND_TO_PINECONE` | `1` to upsert | `0` |
| `CACHE_EMBEDDINGS_TO_DISK` | Save vectors next to chunk JSONL (`*.embeddings.jsonl`) to skip OpenAI on re-upsert when chunk text unchanged | `1` |
| `PINECONE_INDEX_NAME` | Index name | `text-embedding-3-small` |
| `PINECONE_NAMESPACE_DEV` | First upsert target (e.g. dev/staging) | `v3` |
| `PINECONE_NAMESPACE_PROD` | Second upsert target (e.g. production) | `production` |
| `PINECONE_NAMESPACES` | Legacy comma-separated list if DEV/PROD unset | `v3,production` |
| `PINECONE_CLOUD` / `PINECONE_REGION` | Serverless index region (create only) | `aws` / `us-east-1` |
| `OPENAI_API_KEY` | Embeddings + optional span summaries | Required for upsert |
| `PINECONE_API_KEY` | Pinecone | Required for upsert |
| `GENERATE_SUMMARIES` | If **unset** and `SEND_TO_PINECONE=1`: **on** (LLM per span + `summaries=true` upserts). `0`/`false` to skip; `1` to force on | *on when upserting* |
| `SUMMARY_MODEL` | OpenAI chat model for span summaries | `gpt-5-nano` |
| `SUMMARY_PARALLELISM` | Concurrent chat calls per file (1–16); higher = faster, watch rate limits | `4` |
| `SHAREPOINT_BASE_URL` | SharePoint **library folder** URL (same layout as `source_data/`) for per-file `sharepointUrl` at index time; bot can reuse this env name if `SHAREPOINT_LIBRARY_BASE_URL` is unset | Optional |
| `DOTENV_PATH` | Explicit `.env` path inside containers | Optional |

**Terraform alignment:** `pinecone_index_name` stays `text-embedding-3-small` (same index as before). Set `pinecone_namespace` per environment to match the namespace that deployment should query (`v3` for dev, `production` for prod). The indexer still writes to **both** pipeline namespaces when both env vars are set. SharePoint **citation** base URLs for the live bot are **not** set by the indexer — they come from Terraform → Function App (`sharepoint_library_base_url`); see [`../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md`](../.cursor/skills/knowledge-base-curator/citation-sharepoint-links.md).

## Pinecone metadata (vectors)

Stored fields include: `docId`, `fileName`, `sourceRelativePath`, `chunkIndex`, `blockStartIndex`, `blockEndIndex`, `sectionTitle`, `sectionPath`, `pageNumber`, `slideNumber`, `sheetName`, `coordinates`, `sharepointUrl`, `highlightPhrase`, `text`, `summaries` (boolean), etc. Absolute local `filePath` is **not** stored in Pinecone (only in JSONL cache objects).

**Summary spans:** `summary_spans.group_chunks_into_spans` merges whole chunks under one `sectionPath` until ~800 tokens (tunable), then `build_summary_index_objects` writes Polish abstracts. Vector ids look like `{docId}:summary:{0000}`; chunk ids stay `{docId}:{chunkIndex:04d}`.

## Namespace validation (pre-flight)

Before enabling summary-first retrieval in prod, sample the namespace:

```bash
cd pinecone-pipeline
export PINECONE_NAMESPACE=v3   # or production
uv run python scripts/validate_pinecone_namespace.py
```

Optional: `SAMPLE_IDS=docid:0000,docid:0001` to `fetch` specific vector ids. Full duplicate-ID scans are not included (use Pinecone console / export jobs for large indexes).

## Embeddings

- **Model**: `text-embedding-3-small` (OpenAI), **1536** dimensions — must match the Teams bot query embeddings.
- **Local cache** (when `CACHE_EMBEDDINGS_TO_DISK=1`): for each `foo.<docId>.jsonl`, vectors are stored in `foo.<docId>.embeddings.jsonl` under `CHUNK_OUTPUT_DIR`. Entries are keyed by `stableId` and a hash of the exact truncated embedding input; if you change chunk text or the embedding model, delete the sidecar (or clear `chunk_output`) so vectors are recomputed.

## Retrieval helper

```python
from retrieval_helper import search_and_get_full_chunks

results = search_and_get_full_chunks(
    query="your search query",
    index_name="text-embedding-3-small",
    namespace="v3",
    top_k=5,
)
```

## Index and namespace operations

- **Create index**: happens automatically on first upsert (`ensure_index`) if the name does not exist; confirm `PINECONE_CLOUD` / `PINECONE_REGION` match your Pinecone project.
- **Refresh vectors**: re-run the pipeline with `SEND_TO_PINECONE=1`; same `stableId` values overwrite. With local embedding cache enabled, unchanged chunks reuse stored vectors (fewer OpenAI calls); Pinecone still receives an upsert each run.
- **Delete namespace data**: use the Pinecone console or API; there is no single “delete namespace” in the CLI.
- **Delete one indexed document** (chunks + summary spans): `uv run python scripts/delete_corpus_document.py --doc-id <docId>` or `--source-relative-path "5 Instrukcje/foo.pptx"`. Defaults to `PINECONE_NAMESPACE_DEV` + `PINECONE_NAMESPACE_PROD` (or `v3,production`).

## Related documentation

- [`docs/VECTOR-DB-COMPARISON.md`](docs/VECTOR-DB-COMPARISON.md)
- [`../infrastructure/docs/GDPR-MIGRATION-PLAN.md`](../infrastructure/docs/GDPR-MIGRATION-PLAN.md)
- [`../docs/TASKS.md`](../docs/TASKS.md) (task #13)

## Tests

```bash
cd pinecone-pipeline/tests
python -m pytest
```
