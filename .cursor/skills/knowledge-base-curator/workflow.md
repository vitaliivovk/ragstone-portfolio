# Knowledge base workflows (add / edit / delete)

Generic procedures for the **knowledge-base-curator** agent. No project-specific examples.

## Architecture (four surfaces)

| Surface | Purpose | Dev | Prod |
|---------|---------|-----|------|
| `pinecone-pipeline/source_data/` | Source files (local) | same tree | same tree |
| Pinecone index `text-embedding-3-small` | RAG vectors | namespace `v3` | namespace `production` |
| SharePoint `AI/dev/` / `AI/prod/` | Citation links only | mirror paths | mirror paths |
| Bot routing + deploy | Optimizer folder map | dev Function App | prod Function App (`release`) |

**Invariant:** `sourceRelativePath` must match SharePoint layout under `AI/<env>/`.

Summaries (`GENERATE_SUMMARIES=1` at index time) are stored but **not queried** unless `SUMMARY_RETRIEVAL_ENABLED=1` on the Function App (default off).

---

## ADD documents

### A. Plan (approval required)

List each file path, target folder, whether new top-level topic, Pinecone namespaces, SharePoint path, routing edits, branch name.

### B. Corpus

1. Copy files to `pinecone-pipeline/source_data/<Topic>/…`
2. **New top-level topic only:**
   - `pinecone-pipeline/corpus_metadata.py` → `SOURCE_DATA_ROOT_SEGMENTS`
   - `teams-bot/rag/retrieval_filter.py` → `RetrievalScope` + slug constant
   - `teams-bot/bot/status_copy.py` → Polish label
   - `teams-bot/rag/folder_map_prompt.md` → table + routing hints
   - `pinecone-pipeline/tests/test_corpus_metadata.py`
   - `opis folderów.docx` + `source_data/README.md`

### C. Pinecone (dev)

```bash
./scripts/kb.sh reindex "Topic/file1.docx" "Topic/file2.pdf"
```

Unicode paths on Windows: driver script inside container using `os.listdir`.

`.env`: `SEND_TO_PINECONE=1`, `PINECONE_NAMESPACE_DEV=v3`, `PINECONE_NAMESPACE_PROD=` empty.

Optional: `GENERATE_SUMMARIES=0` to skip LLM summary stage (faster; chunks still indexed).

### D. SharePoint (dev citations)

**Human upload** to `Shared Documents/AI/dev/` mirroring `sourceRelativePath` under `source_data/`.

Do **not** run `sharepoint_sync.py` unless the user confirms Graph write access. On access errors → document **human upload** in the plan and changelog.

### E. Bot (if routing changed)

Merge to **`main`** → `scripts/deploy.cmd dev` (or `./scripts/deploy.sh dev`) → user smoke-test.

### F. Prod (second approval, after dev OK)

1. `git checkout release` && merge feature → commit changelog
2. Reindex with `PINECONE_NAMESPACE_PROD=production` (dual upsert OK)
3. SharePoint prod — **human upload** to `AI/prod/`
4. **`deployment-ops`** skill → prod deploy on `release` + changelog

---

## EDIT documents (replace content or rename)

`docId` = hash(path + mtime). In-place edit changes `docId`; old vectors remain until deleted.

### Steps (dev first, approval each phase)

1. **Delete old vectors** (both namespaces when promoting to prod later):

```bash
./scripts/kb.sh delete --source-relative-path "Topic/old.docx"
```

2. Replace file in `source_data/` (keep path if possible)
3. **Reindex with `--force`** (clears local chunk/embed cache):

```bash
./scripts/kb.sh reindex --force "Topic/updated.docx"
```

4. SharePoint overwrite (sync or user)
5. Bot redeploy only if routing/filename rules in prompts changed

**Rename / move:** delete old path in Pinecone → add new path → update SharePoint (delete old + upload new).

---

## DELETE documents

1. **Approve** plan listing path, docId if known, namespaces
2. Pinecone delete (dev; prod only after dev validation if same change set):

```bash
./scripts/kb.sh delete --source-relative-path "Topic/file.pptx"
```

3. Remove file from `source_data/`
4. Optional: remove `chunk_output/*<docId>*`
5. SharePoint: user deletes file (agent may lack delete API)
6. **Whole topic removed:** revert routing/metadata code → dev deploy → prod on `release` after sign-off
7. Handbook (`handbook_corpus.json`): rebuild only if file was in handbook set (rare)

---

## Data integrity risks and checks

See also [SKILL.md § Data integrity](../SKILL.md#data-integrity--always-inform-the-human).

### Before reindex (agent must state to human)

- Is this the **first** index of these paths in the target namespace(s)?
- Was there an earlier index via a **different runtime** (host vs Docker) or after a **file touch** (mtime)?
- If **yes** to either → warn about **orphan duplicates**; plan `delete_corpus_document.py` first unless user declines cleanup.

### After reindex (agent must report)

- Upsert log: `OpenAI embeds` vs `Upserted N vector writes` — if `N ≈ 2 × embeds × num_namespaces`, dual write succeeded.
- If same folder indexed twice in `v3` without delete, expect ~**2×** topic vector count vs `production`.
- Suggest spot-check: filter query or probe for duplicate `sourceRelativePath` with different `docId` in metadata (if visible in audit).

### ADD workflow — integrity notes

Insert in plan step **C**: “If re-running after dev smoke, delete existing vectors for these paths in `v3` before second upsert.”

### EDIT workflow — integrity notes

Steps 1→3 order is **mandatory** (delete → replace file → `--force` reindex). Skipping step 1 **always** warrants an explicit human warning in the plan.

### F. Prod promotion — integrity notes

When promoting after dev-only index:

- Warn: **`production` empty for these paths** until this upsert; **`v3` may already contain vectors** — second upsert to `v3` without delete can duplicate.
- Prefer: upsert **`production` only** (`PINECONE_NAMESPACE_DEV=` empty, `PINECONE_NAMESPACE_PROD=production`) **or** delete in `v3` then single dual upsert.

---

## Verification checklist

- [ ] `./scripts/bot.sh probe "…"` returns expected `corpusTopic` / paths
- [ ] Dev Teams answer cites correct sources
- [ ] App Insights `retrieved_documents` JSON matches
- [ ] Citation links open SharePoint file (dev then prod)
- [ ] Changelog updated with change ID and git SHA
- [ ] **Integrity report** delivered to human (risks + follow-up)
- [ ] User explicitly approved dev → then prod

---

## Human-delegated steps (document in changelog)

| Step | When |
|------|------|
| SharePoint manual upload | Graph auth / Sites.Selected blocked |
| SharePoint delete | Sync script upload-only |
| Dev Teams smoke | Always before prod |
| Prod approval | Explicit user confirmation after dev |
