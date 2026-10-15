# Process / Workflow engine (Office IDE Phase 4)

Scaffolding for **parameterized, versioned process definitions** that run ordered RAG / plugin / LLM steps and produce artifacts (e.g. email drafts). Aligned with the Office IDE roadmap Phase 4 and TASKS **#39** / **#14** (never auto-send).

**Status:** schema + filesystem catalog + dry-run runner + MCP tool stubs. No Azure deploy. No live Graph/send.

| Path | Role |
|------|------|
| [`process_engine/schema.py`](process_engine/schema.py) | Pydantic definition: inputs, steps, output template, never-send |
| [`process_engine/catalog.py`](process_engine/catalog.py) | Versioned filesystem catalog + load/validate |
| [`process_engine/runner.py`](process_engine/runner.py) | Sequential runner with mocked RAG/plugin/LLM |
| [`process_engine/mcp_tools.py`](process_engine/mcp_tools.py) | `list_processes` / `run_process` signatures + handlers |
| [`process_engine/catalog/`](process_engine/catalog/) | Bundled definitions (`standard_client_reply@1`) |
| [`tests/`](tests/) | Schema validation + dry-run unit tests |

Related: [`../mcp-plugins/`](../mcp-plugins/) (plugin scopes), [`../librechat/`](../librechat/) (shell), [`../docs/office-ide/PROCESS-MINING.md`](../docs/office-ide/PROCESS-MINING.md) (Phase 5 mining → promote), task **#39**.

---

## Process definition shape

```json
{
  "id": "standard_client_reply",
  "version": "1",
  "tenant_id": null,
  "title": "…",
  "inputs": [{ "name": "question", "type": "text", "required": true }],
  "steps": [
    { "id": "gather", "type": "rag_query", "query_template": "{{question}}" },
    { "id": "sp", "type": "plugin_call", "plugin": "sharepoint", "tool": "sharepoint_search", "scope": "search", "arguments": {} },
    { "id": "compose", "type": "llm_transform", "prompt_template": "…", "input_refs": ["gather"] }
  ],
  "output_template": {
    "artifact_type": "email_draft",
    "subject_template": "…",
    "body_template": "…",
    "never_send": true
  }
}
```

Step types: `rag_query` | `plugin_call` | `llm_transform`.

**Never-send policy:** `email_draft` artifacts require `never_send: true`. The runner refuses to emit a sendable email artifact. Plugin step scopes are limited to `read` / `search` / `draft` (no `send`).

JSON Schema export: `ProcessDefinition.model_json_schema()` / `process_engine.schema.process_json_schema()`.

---

## Catalog layout

```
process_engine/catalog/
  <process_id>/
    <version>.json
```

Folder name must equal `id`; filename stem must equal `version`.

```python
from process_engine import ProcessCatalog, load_process

catalog = ProcessCatalog()  # bundled catalog
definition = catalog.get("standard_client_reply")  # latest
definition = catalog.get("standard_client_reply", "1")
```

---

## Dry-run the example process

```bash
cd process-engine
python -m pip install -e ".[dev]"
python -m process_engine.cli standard_client_reply
# or:
python -m process_engine.cli standard_client_reply \
  --input client_name="Acme" \
  --input client_email="a@example.com" \
  --input topic="kaucja" \
  --input question="Jak zwrócić kaucję?"
pytest -q
```

Demo defaults fill `standard_client_reply` inputs when omitted. Output JSON includes `artifact` (`never_send: true`) and per-step mock traces.

---

## MCP exposure (`list_processes`, `run_process`)

Tool metadata + handlers live in [`process_engine/mcp_tools.py`](process_engine/mcp_tools.py). Thin registration helper for the Phase 3 HTTP stub: [`../mcp-plugins/mcp_plugins/processes/`](../mcp-plugins/mcp_plugins/processes/).

```python
from process_engine.mcp_tools import LIST_PROCESSES_TOOL, RUN_PROCESS_TOOL, handle_tool_call

handle_tool_call("list_processes", {})
handle_tool_call(
    "run_process",
    {
        "process_id": "standard_client_reply",
        "inputs": {
            "client_name": "Acme",
            "client_email": "a@example.com",
            "topic": "kaucja",
            "question": "Jak zwrócić kaucję?",
        },
    },
)
```

Wire into LibreChat later via `mcpServers` (same streamable-http pattern as SharePoint/Teams). Scope: `list_processes` = `read`, `run_process` = `draft`.

---

## Out of scope (v1 scaffold)

- Live RAG adapter or Graph plugin calls
- Conversational parameter collection UI
- Visual process builder / mining (Phase 5)
- Deploy to Container Apps
