# Teams plugin stub

| Tool | Scope | Notes |
|------|-------|-------|
| `teams_list_chats` | search | OBO delegated |
| `teams_read_messages` | read | No message bodies in audit |
| `teams_draft_message` | draft | Returns draft payload only |
| `teams_post_message` | send | Always denied in v1 (`never_send_v1`) |

Current-chat bot replies remain Bot Framework — not this plugin.
