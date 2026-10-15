# Outlook plugin stub

Tool signatures live in [`server.py`](server.py). No live Graph.

| Tool | Scope | Notes |
|------|-------|-------|
| `outlook_search_messages` | search | OBO delegated `Mail.Read` when wired |
| `outlook_read_message` | read | Cap body preview; no bodies in audit |
| `outlook_draft_message` | draft | Creates draft only — never sends |
| `outlook_send_message` | send | Always denied in v1 (`never_send_v1`) |

Aligned with TASKS **#14** / **#14c**. Process engine “standard client reply” should land here as a **draft**, not send.

**Onyx harvest:** later extract MIT Outlook connector API patterns only.
