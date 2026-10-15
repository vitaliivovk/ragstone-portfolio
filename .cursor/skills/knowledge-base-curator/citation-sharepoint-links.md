# Citation links and SharePoint

How **clickable document links** in the **Źródła** block are built at runtime, and **where to change** URLs, folders, and Terraform so dev/prod stay consistent.

## How it works (runtime)

1. **Pinecone** returns chunk metadata on each retrieval. Important fields:
   - **`sourceRelativePath`** — path under the corpus root (`pinecone-pipeline/source_data/`), e.g. `3 Mieszkania z vatem- najem zwykły/…/file.docx`. Primary key for building a file URL when no full URL is stored on the vector.
   - **`sharepointUrl`** (optional) — full document URL, set at **index time** if the pipeline ran with `SHAREPOINT_BASE_URL` pointing at the SharePoint library folder that mirrors `source_data/`.
   - **`fileName`**, **`pageNumber`**, **`highlightPhrase`**, etc. — labels and deep-link query parameters (`?web=1&find=…` for Office files, `?page=` for PDFs).

2. **URL resolution** (see [`teams-bot/rag/citations.py`](../../../teams-bot/rag/citations.py)):
   - If **`sharepointUrl`** is present on metadata → use it.
   - Else combine **`SHAREPOINT_LIBRARY_BASE_URL`** (or, if unset, **`SHAREPOINT_BASE_URL`**) with **`sourceRelativePath`**: each path segment is URL-encoded and appended to the base (no trailing slash on base required).

3. **Teams rendering** — final bot activities set **`textFormat: markdown`** so `[label](url)` in **Źródła** renders as a clickable link where the client supports it.

**Invariant:** The folder tree under the SharePoint **library base URL** must match **`sourceRelativePath`** segment-for-segment (same names, same nesting). If files live only under `…/AI/v3/` but the Function App points at `…/AI/dev/`, links will 404 until the mirror exists or the base URL is corrected.

## Where to change configuration

| What you want | Where to change |
|----------------|-----------------|
| **Azure dev / prod** base URL for citations (recommended) | [`infrastructure/environments/dev.tfvars`](../../../infrastructure/environments/dev.tfvars) and [`prod.tfvars`](../../../infrastructure/environments/prod.tfvars) — variable **`sharepoint_library_base_url`**. Applied as **`SHAREPOINT_LIBRARY_BASE_URL`** in [`infrastructure/functions.tf`](../../../infrastructure/functions.tf). Deploy: `./scripts/terraform.sh <dev\|prod> apply` (see [`infrastructure/README.md`](../../../infrastructure/README.md)). |
| **Variable definition / default** | [`infrastructure/variables.tf`](../../../infrastructure/variables.tf) — `sharepoint_library_base_url` |
| **Local bot** (`func host` / tests) | [`teams-bot/local.settings.json.example`](../../../teams-bot/local.settings.json.example) or repo [`.env.example`](../../../.env.example) |
| **Bake full `sharepointUrl` on every vector** (optional) | Pipeline env **`SHAREPOINT_BASE_URL`** — see [`pinecone-pipeline/README.md`](../../../pinecone-pipeline/README.md) |
| **Upload / refresh files in SharePoint** | [`scripts/sharepoint_sync.py`](../../../scripts/sharepoint_sync.py) — **`--remote-prefix`** must match library base (`dev` / `prod`). See [`scripts/README.md`](../../../scripts/README.md). |
| **Link format / encoding logic** | [`teams-bot/rag/citations.py`](../../../teams-bot/rag/citations.py) — `resolve_sharepoint_document_url`, `build_sharepoint_link`, `format_citation` |

**Not applied by `deploy-fast.sh` alone:** changing **only** `*.tfvars` requires **`terraform apply`**. `deploy-fast.sh` syncs **Pinecone** settings only, not **`SHAREPOINT_*`**.

## Environment layout (current convention)

| Environment | Example library suffix (under `Shared Documents`) | Terraform tfvars |
|-------------|-----------------------------------------------------|------------------|
| **dev** | `AI/dev` | `infrastructure/environments/dev.tfvars` |
| **prod** | `AI/prod` | `infrastructure/environments/prod.tfvars` |

Pinecone **namespace** (`v3` vs `production`) is separate from the SharePoint folder name; only **relative file paths** under `source_data/` must align with `AI/dev` or `AI/prod`.

## Operational checklist

1. Set **`sharepoint_library_base_url`** in **`environments/*.tfvars`** and **`terraform apply`**.
2. Human upload or `sharepoint_sync.py` with **`--remote-prefix dev`** or **`prod`** matching that URL.
3. Smoke-test in Teams: **Źródła** entries open the correct document.

## Related

- [`docs/TASKS.md`](../../../docs/TASKS.md) — task **5** (SharePoint deep links)
