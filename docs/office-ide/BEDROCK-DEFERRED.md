# Deferred track: AWS Bedrock / EU-GDPR

**Status:** deferred parallel track — **does not block** the LibreChat web shell, MCP plugins, or process engine.

When executed, the swap happens **inside the RAG service** only. LibreChat still talks to the OpenAI-compatible facade (`/v1/chat/completions`); MCP and processes are unchanged.

## Source docs

| Doc | Role |
|-----|------|
| [`infrastructure/docs/GDPR-MIGRATION-PLAN.md`](../../infrastructure/docs/GDPR-MIGRATION-PLAN.md) | Bedrock Claude (Frankfurt), EU embeddings, vector storage migration phases |
| [`pinecone-pipeline/docs/VECTOR-DB-COMPARISON.md`](../../pinecone-pipeline/docs/VECTOR-DB-COMPARISON.md) | OpenSearch managed EU vs Pinecone EU; hybrid search context (task **28**) |

Also tracked under TASKS **#12** / **#28** and Office IDE roadmap §7.

## Shell unaffected

- LibreChat config, Entra OIDC, Mongo history — no provider change.
- MCP plugins (Graph / Salesforce) — independent of LLM/embedding vendor.
- Process engine — callouts stay “RAG query / plugin / LLM transform”; only the RAG service’s LLM client changes.

## Fix embedding one-model rule (blocking bug in the GDPR plan)

The current GDPR plan drafts **different** embedding models for index vs query:

- Index: local `multilingual-e5-large`
- Query: Bedrock Titan V2

Those are **incompatible vector spaces** — retrieval would silently degrade. **Rule:** use **one** embedding model on **both** sides (Titan V2 everywhere, or e5-large everywhere). Either path needs a full re-index and dimension alignment (e.g. 1536 → 1024). Fix this in the migration plan before any cutover.

## Claude Polish eval gate

Bedrock Claude requires Polish prompt re-tune. **Do not** cut over until:

1. Golden / acceptance questions pass on the Claude stack (bot-quality-evaluation skill).
2. Spot-check App Insights `RAG_TURN_AUDIT` for routing + citation quality vs the current OpenAI baseline.

Eval is the go/no-go — not infra alone.

## When triggered (swap checklist)

1. Fix one-model embedding rule in plan + pipeline.
2. Bedrock Claude client behind the existing RAG graph (`ChatBedrockConverse` or equivalent).
3. Re-index to chosen EU vector store (OpenSearch or Pinecone EU).
4. Run Claude Polish golden gate.
5. Flip adapter internals; leave shell + MCP + processes untouched.
