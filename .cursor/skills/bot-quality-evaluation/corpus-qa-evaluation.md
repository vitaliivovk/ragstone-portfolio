# RAG corpus Q&A evaluation (2026-04)

This note records a **grounded** quality check: questions were tied to **specific indexed chunks** (same parsing as `ragstone-index`), then run through the **live Teams bot RAG stack** and, separately, **Pinecone-only** similarity search.

## Method

1. **Chunk export for agents**  
   From repo root:  
   `./scripts/kb.sh qa-export --seed 42`  
   Produces `agent_exports/corpus_qa_for_cursor.md` (gitignored). Each section lists chunk excerpts; a human or agent fills one Polish Q&A per document from **those excerpts only**.

2. **End-to-end RAG**  
   `./scripts/bot.sh rag --file logs/corpus_qa_questions.txt` (six Polish questions). Same code path as Azure Functions: optimizer → Pinecone → LLM.  
   On Windows, set `PYTHONIOENCODING=utf-8` if the console cannot print Polish characters.

3. **Vector DB only**  
   `./scripts/bot.sh probe -f logs/corpus_qa_questions.txt -k 8` — `asimilarity_search_with_score`, **no** optimizer or generator. Compares **ranking** of chunks (scores are index-specific; ranks matter more than absolute values).

## Retrieval configuration (summary-first, wider k)

- The **optimizer** chooses `num_documents` in **10–20** (default **12**); used as chunk/evidence budget and scales summary stage-1 `top_k`.  
- **`retrieval_tier`:** `summary_then_chunks` (when optimizer chooses it) would run Pinecone with `summaries=true` first, then load chunk rows for `chunkIndexStart`–`chunkIndexEnd`; falls back to chunk-only search if no summary hits. **`SUMMARY_RETRIEVAL_ENABLED`** defaults to **off** in bot code when unset (chunk-only regardless of tier). Set **`SUMMARY_RETRIEVAL_ENABLED=1`** to enable the summary-first stage.  
- **Neighbor expansion:** each retrieved chunk row also fetches `chunkIndex ± 1` in the same `docId` (Pinecone `fetch`), then context is capped (~`MAX_RAG_CONTEXT_CHARS` in `teams-bot/rag/nodes.py`).  
- On optimizer failure, fallback strategy uses **12** chunks and **`summary_then_chunks`**.  
- Legacy `teams-bot/rag/chain.py` / `RAGChain` was **removed** — only **`RAGGraph`** remains.

## Chunk boundaries (indexing)

Chunks are built in `pinecone-pipeline/document_parser/chunking.py` via `merge_units_into_chunks`: units are merged until roughly **`target_tokens` (default 300)**, with **~15% overlap**; **headings** flush a chunk. Each merged block is one vector (`chunkIndex` in metadata).

**Implication:** A fact at the start of a long GDPR annex (e.g. “Administratorem jest … **biuro@…**”) may live in **chunk 0**, while a query embedding may match **chunk 1** (middle of the same file) more strongly. The **file** can be correct while the **top-k chunks** omit the sentence the user asked about.

## End-to-end RAG results (six questions)

| # | Theme | Outcome | Notes |
|---|--------|---------|--------|
| 1 | Reservation fee — deadline and effect of non-payment | **Pass** | Correct 3 business days and automatic termination; scoped retrieval hit the reservation template. |
| 2 | Contacting the DPO (IOD) from an annex | **Mostly pass** | Phone and email correct; typo **Javorska** vs **Jaworska**; unfiltered retrieval favored **pl-ua** PDF variants over Polish “Najem F” — same contact details, different files. |
| 3 | Minimum notice to vacate (14 days) | **Partial** | **14 days** correct; extra legal steps (court / enforcement) went beyond the notarial VAT annex snippet used for grounding; retrieval ranked **Najem I** lease chunks above the **VAT Załącznik 10** notarial chunk for that wording. |
| 4 | Where to mark lease termination in CRM | **Pass** | Matched internal instruction (“Obsługa Najmu”, related tabs, documents). |
| 5 | Data controller name + Administrator email | **Fail** | Model claimed information was missing despite retrieval returning **RODO annex** chunks — see Pinecone section (**wrong chunk within file**). |
| 6 | Discount card — format, address, cost | **Pass** | Free, PDF to e-mail; aligned with regulations. |

**Operational notes from the run:** OpenAI **429** retries occurred under burst traffic; harness may still **write conversation rows** to Azure Table Storage even with `--no-history` — use a dedicated `--user-id` for isolated tests.

## Pinecone-only findings

- **Q1 (reservation):** Top hits were the correct **reservation contract** chunks (fee and termination). Some **Instrukcje** noise lower in the list (shared vocabulary “rezerwacyjn”).  
- **Q2 (IOD):** Unfiltered top hits were **Ukrainian** “Najem I” RODO PDFs (IOD phone/email in UA text). With filter **`2_najem_firma`**, top hits were the expected **Załącznik 5 Najem F** `.docx` files.  
- **Q3 (14 days):** Unfiltered ranks **1–4** were **Najem I** `chunkIndex=8` variants; the **VAT notarial Załącznik 10** appeared around **rank 6**. With **`3_mieszkania_z_vatem_najem_zwyky`**, Załącznik 10 rose but **did not always outrank** other VAT lease chunks — explains partial RAG behavior when `k=4` and scope is `all`.  
- **Q4 (termination UI):** Top hits were **`umowy do wypowiedzenia.pdf`** — strong.  
- **Q5 (controller + email):** Top hits were the **right document type** but often **`chunkIndex=1`** (mid-annex boilerplate), not **chunk 0** (header with company name and `office@example.com`). Scoped **`1_najem_instytucjonalny`** still surfaced **chunk 6** (recipient lists) ahead of the defining paragraph — classic **chunk-boundary** effect, not “Pinecone empty.”  
- **Q6 (Northwind Club):** Top hit **`Regulamin karty rabatowej … PL.pdf` chunk 0** — strong.

## Conclusions

1. **Pinecone + `text-embedding-3-small`** generally returns the **right corpus area** for these questions.  
2. **Failure modes** are mostly **(a)** semantic neighbors (RODO vs RODO, PL vs UA duplicates), **(b)** **top-k too small** for the true chunk rank, **(c)** **chunking** placing the answer in a different vector than the one the query matches best.  
3. **Improvements to try** (product / R&D): raise **k** or add **reranking** for GDPR-style questions; **MMR** to diversify duplicates; optional **query variants** (e.g. “nagłówek administrator danych”); ingest-time **metadata** for annex type / language if filters should prefer PL over pl-ua; re-chunking or **prefix boost** for first section of long forms (heavier change).

## Related code and docs

| Artifact | Role |
|----------|------|
| `./scripts/kb.sh qa-export` | Generates `corpus_qa_for_cursor.md` |
| `./scripts/bot.sh rag` | Local full RAG harness |
| `./scripts/bot.sh probe` | Direct Pinecone similarity + optional `corpusTopic` filter |
| [`teams-bot/rag/optimizer.py`](../../../teams-bot/rag/optimizer.py) | `num_documents` 10–20, `retrieval_tier` |
| [`teams-bot/rag/nodes.py`](../../../teams-bot/rag/nodes.py) | Summary-first retrieve, neighbor expansion, context cap |
| [`pinecone-pipeline/summary_spans.py`](../../../pinecone-pipeline/summary_spans.py) | Span grouping + summary text for `summaries=true` vectors |
| [`pinecone-pipeline/document_parser/chunking.py`](../../../pinecone-pipeline/document_parser/chunking.py) | Chunk merge / token target |
| [TASKS.md — Task 16](../../../docs/TASKS.md) | Ongoing retrieval-quality task |
| [acceptance-criteria.md](acceptance-criteria.md) | Northwind A1–B5 MUST/SHOULD checklist |
