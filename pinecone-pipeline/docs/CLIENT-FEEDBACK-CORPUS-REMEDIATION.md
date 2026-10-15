# Client feedback — corpus remediation checklist

**Wave 3** companion to [acceptance-criteria.md](../../.cursor/skills/bot-quality-evaluation/acceptance-criteria.md).  
Track owner updates and reindex steps here. Contract/template PDF edits remain out of scope unless explicitly requested.

---

## Procesy deck removal (2026-05-28) — done

Stale **`Procesy_ NW RENT_pl 2025.pptx`** conflicted with Instrukcja 2025 and contract docs (deposit tiers, early termination, foreigners/PESEL). Removed end-to-end:

| Layer | Action |
|-------|--------|
| **Corpus file** | Deleted `pinecone-pipeline/source_data/5 Instrukcje/Procesy_ NW RENT_pl 2025.pptx` |
| **Local chunks** | Deleted `chunk_output/Procesy__VD_RENT_pl_2025.*.jsonl` (+ embeddings sidecar) |
| **Pinecone** | `delete_corpus_document.py --doc-id fe6415f8232fe888b26df486c9ea90e818449c9c` on index `text-embedding-3-small`, namespaces **`v3`** and **`production`** |
| **Handbook direct** | `handbook_corpus.json` rebuilt — **Instrukcja 2025 only** (`scripts/build_handbook_corpus.py`) |
| **Anchor retrieval** | Default `RAG_ANCHOR_SOURCE_RELATIVE_PATHS` → Instrukcja PDF only (`teams-bot/rag/anchor_documents.py`) |
| **Agent prompts** | Optimizer / handbook / answer composer — no routing to Procesy deck (`d134463`) |

**Not changed:** opening paragraph inside **Instrukcja dla nowego pracownika 2025.pdf** still mentions reading the Procesy deck on SharePoint (source text unchanged).

**Repeat delete (if vectors reappear):**

```bash
cd pinecone-pipeline
uv run python scripts/delete_corpus_document.py --doc-id fe6415f8232fe888b26df486c9ea90e818449c9c
# or: --source-relative-path "5 Instrukcje/Procesy_ NW RENT_pl 2025.pptx"
```

**Verify Pinecone:** filtered query on `docId` or `sourceRelativePath` → 0 matches in `v3` and `production`.

**Verify bot (dev):** deposit / early-termination / verification questions — citations should not include `Procesy_ NW RENT_pl 2025.pptx`; handbook path uses Instrukcja only.

**Deploy bot (dev):** branch `feature/client-feedback-investigation-2026-05` (commits `d134463` code + `95ef5fc` docs). From repo root with Docker Desktop + `az login` in dev container:

```powershell
.\scripts\deploy.sh dev
```

Pinecone vectors were already deleted in **`v3`**; deploy only updates Function App code (`handbook_corpus.json`, anchor paths, prompts). No re-index needed for removal.

---

## P0 — stale or conflicting sources (reindex after owner fix)

| Priority | Source (indexed path) | Issue IDs | Problem | Owner action |
|----------|----------------------|-----------|---------|--------------|
| P0 | ~~`pinecone-pipeline/source_data/.../Procesy_ NW RENT_pl 2025.pptx`~~ **removed 2026-05-28** | A2, A3, A7, A8, A16, A17 | Stale deck (3-mo deposit, ½/3× termination, manual-only foreigners) | **Removed from corpus + Pinecone**; rely on Instrukcja 2025 + contracts |
| P0 | `Wzór umowy najmu I PL` (porozumienie §) | A4, A6, A16 | Max **3** months vs tester expectation **4** for some scenarios | Legal/commercial sign-off; update template or bot guidance |
| P0 | `Przedłużenie (W/N/R)` §4.8 | A6, A17 | **4-month** cap for ≥2y extensions (gold for long contracts) | Ensure retrieval ranks extension doc for 24/36m questions |
| P0 | `Instrukcja dla nowego pracownika 2025` + `przykladowe_tresci_maili` | A15, B2 | Gold deposit guidance present but buried / handbook bypass | Keep in corpus; primary handbook source after Procesy removal |
| P0 | `Instrukcja dla nowego pracownika 2025` §4.2 (page ~10) | A7, A15, B2 | Deposit guidance after verification only referenced “mapa procesu”; missing Northwind deposit example | **Patched 2026-05-29** — see below |

---

## Instrukcja 2025 — Northwind deposit example (2026-05-29)

Added explicit kaucja matrix after *„Wysokość kaucji wynika wprost w wyniku weryfikacji klienta”* in **DOCX** + re-exported **PDF** (LibreOffice Docker).

| Layer | Action |
|-------|--------|
| **Corpus** | `pinecone-pipeline/source_data/5 Instrukcje/Instrukcja dla nowego pracownika 2025.docx` + `.pdf` |
| **Patch script** | `pinecone-pipeline/scripts/patch_instrukcja_kaucja.py` |
| **Pinecone** | Old `docId`s deleted; reindexed DOCX `9e581f5554e516be8a2d2e89cd7610c2c76e4810`, PDF `7e6c66f2ecb272bb6e1b7c5768903596e1686b5a` → namespaces **`v3`** + **`production`** |
| **Handbook** | `scripts/build_handbook_corpus.py` (newest PDF JSONL) → `teams-bot/rag/handbook_corpus.json` |
| **SharePoint** | Operator: upload both files under `AI/prod/5 Instrukcje/` (device auth or app grant) |

**Reindex one document (local):**

```bash
cd pinecone-pipeline
SEND_TO_PINECONE=1 GENERATE_SUMMARIES=1 uv run python scripts/reindex_files.py --force \
  "5 Instrukcje/Instrukcja dla nowego pracownika 2025.docx" \
  "5 Instrukcje/Instrukcja dla nowego pracownika 2025.pdf"
```

**Docker (from repo root):** `docker compose -f docker-compose.pinecone.yml run --rm pinecone-indexer uv run python scripts/reindex_files.py --force "5 Instrukcje/…"`

**PDF export (no local Word):**

```bash
docker run --rm -v "$PWD/pinecone-pipeline/source_data:/data" linuxserver/libreoffice \
  libreoffice --headless --convert-to pdf --outdir "/data/5 Instrukcje" \
  "/data/5 Instrukcje/Instrukcja dla nowego pracownika 2025.docx"
```

**Verify chunks:** grep `Weryfikacja przez Northwind` in `chunk_output/Instrukcja_dla_nowego_pracownika_2025.*.jsonl`.

---

## P1 — retrieval / generation (no file edit)

| Item | Issue IDs | Mitigation (code / ops) |
|------|-----------|-------------------------|
| Narrow `retrieval_scope` for tenant fee questions | A5, A17 | Optimizer scope rules; KQL `scripts/kql/prod_client_feedback_misroute.kql` |
| Clarification gate (first lease vs extension; individual vs company) | A9, A13, B4 | `RAGStrategy.clarification_needed` — Wave 3 |
| Topic answer composer (kaucja, weryfikacja, wcześniejsze rozwiązanie) | B2, B3, A7 | `teams-bot/rag/answer_composer.py` — Wave 3 |
| Hybrid search + freshness metadata | B5, A8 | Task **28** in [TASKS.md](../../docs/TASKS.md); vendor notes in [VECTOR-DB-COMPARISON.md](VECTOR-DB-COMPARISON.md) |

---

## Reindex steps (after source updates)

1. Place updated files under `pinecone-pipeline/source_data/` (same relative paths as today).
2. Regenerate chunks: pipeline ingest for affected documents only (full regen if unsure).
3. Verify `pinecone-pipeline/chunk_output/*.jsonl` — grep for stale phrases (`kaucja 3 m-ce`, `max 3×` on wrong slide).
4. Upsert to dev namespace (`v3`); run golden repro: `teams-bot/logs/client_feedback_golden.txt` via `teams-bot/scripts/run_local_rag_tests.py`.
5. Promote to `production` namespace after sign-off; monitor `RAG_TURN_AUDIT` with May feedback KQL pack.

---

## Out of scope (document, do not index as FAQ)

| Topic | Issue IDs |
|-------|-----------|
| Rent-default insurance (only OC in corpus) | A12 |
| Company VAT subsidy on rent | A19 |
| Notarial cap “roczny czynsz + opłaty eksploatacyjne” if absent from chunks | A1 |
