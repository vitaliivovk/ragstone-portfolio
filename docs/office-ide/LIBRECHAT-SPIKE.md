# LibreChat spike checklist (Phase 0)

Spike for the Office IDE web shell. Soft-fork only (config / image / small additive patches). RAG stays on **OpenAI + Pinecone**; Bedrock/GDPR is deferred.

Related: [FRONTEND-EXIT-CRITERIA.md](FRONTEND-EXIT-CRITERIA.md), [`librechat/README.md`](../../librechat/README.md), task **39** in [`docs/TASKS.md`](../TASKS.md).

## 1. Local LibreChat stand-up

- [ ] Clone or pull LibreChat upstream; build **own** Docker image (no secret forks of core).
- [ ] Apply repo config from [`librechat/`](../../librechat/) (`librechat.yaml` + `.env` from `.env.example`).
- [ ] Point the single custom endpoint at the Phase 1 adapter (`http://host.docker.internal:8081/v1` or equivalent).
- [ ] Confirm chat UI loads with **one** model only (no model picker / marketplace noise).

## 2. Entra OIDC

- [ ] Register Entra app (OIDC); set `OPENID_ISSUER` to tenant-specific issuer.
- [ ] `ALLOW_REGISTRATION=false`; `OPENID_REQUIRED_ROLE` (or equivalent app-role gate).
- [ ] `OPENID_REUSE_TOKENS=true` for SharePoint picker / OBO later.
- [ ] Login works for in-tenant users with the required role; outsiders rejected.

## 3. SSE streaming

- [ ] Adapter `stream: true` → LibreChat renders incremental answer tokens.
- [ ] Non-stream path still works for debugging (`stream: false`).
- [ ] Long answers do not stall or double-deliver (compare vs Teams TTFT qualitatively).

## 4. `reasoning_content` status lines

- [ ] Polish status strings (from `bot/status_copy.py`) appear as thinking/reasoning UI via `reasoning_content` (LibreChat `customParams.reasoningKey`).
- [ ] Status updates before first answer token (analyze / plan / retrieve / compose).
- [ ] Answer text is **not** mixed into reasoning; citations stay in content.

## 5. Header templating

- [ ] LibreChat sends `X-User-ID: {{LIBRECHAT_USER_OPENIDID}}`.
- [ ] LibreChat sends `X-Conversation-ID: {{LIBRECHAT_BODY_CONVERSATIONID}}`.
- [ ] Adapter uses these for context-cache + `/style` preferences (not Table Storage chat history).
- [ ] Document that web Entra oid and Teams `29:…` ids are **separate** spaces in v1.

## 6. Curated agents config

- [ ] `interface.agents.use: true`, `create: false`, `share: false`.
- [ ] `temporaryChat: false`, `marketplace: false`, `modelSelect: false`, `presets: false`, `parameters: false`.
- [ ] Polish `customWelcome` shown on empty chat.
- [ ] Bundled `rag_api` (pgvector) disabled or limited to ad-hoc file chat only.

## 7. SharePoint file picker

- [ ] `ENABLE_SHAREPOINT_FILEPICKER` (+ delegated `Files.Read.All`, `AllSites.Read`, `access_as_user`).
- [ ] Dev-tenant pick → file context reaches the turn (spike note: may be LibreChat-side only until MCP).
- [ ] Confirm OBO token reuse does not break chat endpoint auth (API key to adapter is separate).

## 8. Mongo hosting decision

Choose one for Phase 2 Terraform; record decision below after spike.

| Option | Pros | Cons | Spike probes |
|--------|------|------|--------------|
| **Cosmos DB for MongoDB vCore** | Azure-native, same billing/tenant | LibreChat driver quirks; version/feature gaps | Create empty DB; LibreChat migrations; CRUD conversations |
| **MongoDB Atlas (EU)** | Full Mongo compat | Third-party DPA; extra vendor | Same smoke; confirm EU region |

**Decision criteria:** (1) LibreChat starts and persists threads; (2) EU data residency acceptable; (3) ops cost at ~100 users; (4) Terraform repeatability.

**Terraform (after decision):** [`infrastructure/docs/LIBRECHAT-HOSTING.md`](../../infrastructure/docs/LIBRECHAT-HOSTING.md) + stubs in [`infrastructure/librechat.tf`](../../infrastructure/librechat.tf) (`librechat_mongo_provider`, commented Cosmos vCore).

**Decision (fill in):** _pending spike_ — date / owner / choice / notes.

## 9. MIT legal sign-off checklist

- [ ] Confirm LibreChat license remains **MIT** for the pinned upstream tag/commit.
- [ ] Soft-fork policy: config + own image + ≤ ~6 meaningful patches; no GPL/copyleft deps added.
- [ ] Onyx/Danswer: harvest **MIT core** connectors only; never copy `ee/`.
- [ ] No Open WebUI / Dify as base (rejected — branding / multi-tenant license).
- [ ] Legal/compliance owner initials + date: ________

## Spike outcome log

| Item | Result | Date |
|------|--------|------|
| Local stand-up | | |
| Entra OIDC | | |
| SSE | | |
| reasoning_content | | |
| Headers | | |
| Curated UI | | |
| SharePoint picker | | |
| Mongo choice | | |
| Legal sign-off | | |
