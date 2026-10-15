# Microsoft Teams chat history vs. Azure Table Storage

## Current architecture

The Northwind Residences Teams bot (`teams-bot/function_app.py`) receives each message as a Bot Framework activity over HTTP. Conversation turns are persisted in **Azure Table Storage** (`TableStorageMemory`, table `conversations`) keyed by Teams user id, and the last RAG retrieval is cached in table `conversation_context` (`ContextCache`). History is loaded before each turn in `RAGGraph.load_history` / `build_teams_pipeline`.

## Goal

Avoid duplicating chat history in our own database by reading messages directly from Microsoft Teams / Microsoft Graph.

## Microsoft Graph APIs (reference)

- **List messages in a chat:** `GET https://graph.microsoft.com/v1.0/chats/{chat-id}/messages`  
  See [List messages in a chat](https://learn.microsoft.com/en-us/graph/api/chat-list-messages).
- **Channel messages:** `GET /teams/{team-id}/channels/{channel-id}/messages` (and related APIs).

Application context for reading chat messages typically requires **Resource-Specific Consent (RSC)** declared in the Teams app manifest (manifest v1.6+), e.g. `ChatMessage.Read.Chat` for chats and `ChannelMessage.Read.Group` for channels. See [Resource-specific consent for Teams apps](https://learn.microsoft.com/microsoftteams/platform/graph-api/rsc/resource-specific-consent) and [Get all channel and chat messages for bots](https://learn.microsoft.com/microsoftteams/platform/bots/how-to/conversations/channel-messages-for-bots-and-agents).

## Blocker: personal (1:1) bot scope

From [Resource-specific consent for apps](https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/rsc/resource-specific-consent) (RSC permissions table for chat/meeting):

> The RSC permissions for chat in **personal scope** is limited to `ChatMessageReadReceipt.Read.Chat`.

So in **personal** scope (typical 1:1 chat between the user and the bot), RSC does **not** expose `ChatMessage.Read.Chat` for reading message bodies. That permission applies in group chat / meeting contexts, not for the primary employee↔bot 1:1 scenario (`conversationType` personal; see `teams-bot/bot/activity_handler.py`).

Without RSC read access to message bodies in personal chats, the bot cannot reconstruct prior turns from Graph using the same consent model tenants expect for an internal assistant.

## Alternatives (rejected for this product)

| Approach | Why not |
|----------|---------|
| **Application permission `Chat.Read.All`** | Reads every chat in the tenant; requires broad admin consent; unacceptable surface for an internal HR/procedures bot. |
| **Delegated `Chat.Read` + user sign-in** | Requires interactive OAuth per user inside Teams; breaks “open bot and ask” UX. |

## Throttling (would apply if Graph read were available)

Per [Microsoft Graph throttling limits — Teams](https://learn.microsoft.com/en-us/graph/throttling-limits), e.g. `GET 1:1/group chat message` is limited (e.g. per-app-per-tenant and per-chat limits). Not the binding constraint here because personal-scope read is blocked as above.

## Decision

- **Keep** Azure Table Storage for conversation history and RAG context cache.
- **Expose** a user-triggered reset: `/clean_chat_history` (and aliases) in `process_message`, clearing `conversations` and `conversation_context` for that user.
- **Revisit** Graph-backed history only if the product moves to **group chat / channel**-first deployment where `ChatMessage.Read.Chat` RSC is applicable and consent is acceptable.

## Related code

- `teams-bot/rag/memory.py` — `clear_history`
- `teams-bot/rag/context_cache.py` — `clear_user_context`
- `teams-bot/function_app.py` — slash-command handler before `TeamsStreamer`
