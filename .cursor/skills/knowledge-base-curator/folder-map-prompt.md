# Folder map prompt (optimizer)

## Source of truth

- **Binary:** [`pinecone-pipeline/source_data/opis folderów.docx`](../../../pinecone-pipeline/source_data/) — human-authored description of folders/files (Vlad).
- **Prompt text:** [`teams-bot/rag/folder_map_prompt.md`](../../../teams-bot/rag/folder_map_prompt.md) — Markdown appended to the RAG **optimizer** system prompt in [`teams-bot/rag/optimizer.py`](../../../teams-bot/rag/optimizer.py) via [`teams-bot/rag/folder_map_loader.py`](../../../teams-bot/rag/folder_map_loader.py).

## When to update

Whenever **`pinecone-pipeline/source_data/`** folder layout or business meaning changes, or when the DOCX description changes: edit **`folder_map_prompt.md`** (and refresh the DOCX in `source_data/` if that is your authoring workflow).

## Indexing

The folder map is **not** required to be embedded in Pinecone unless you choose to ingest it; it is primarily a **routing hint** for the optimizer LLM.
