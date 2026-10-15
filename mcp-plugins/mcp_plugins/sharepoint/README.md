# SharePoint plugin stub

Tool signatures live in [`server.py`](server.py). No live Graph.

| Tool | Scope | Notes |
|------|-------|-------|
| `sharepoint_list_sites` | search | Delegated OBO when wired |
| `sharepoint_browse_folder` | read | Path allowlist planned under `AI/` for app-only |
| `sharepoint_read_file` | read | Cap `max_bytes`; no body in audit |

**Sites.Selected vs delegated:** see TASKS **#35** (app-only headless) and **#14c** (OBO for user mailbox/files). LibreChat SharePoint *file picker* is separate (LibreChat built-in OBO) from this MCP plugin.

**Onyx harvest:** later extract MIT SharePoint connector API patterns only — do not copy indexer or EE permission sync.
