# Bot quality evaluation — procedures

**Acceptance checklist:** [acceptance-criteria.md](acceptance-criteria.md). **Corpus Q&A study:** [corpus-qa-evaluation.md](corpus-qa-evaluation.md).

## KQL (dev container)

```bash
./scripts/kql.sh -o table scripts/kql/last_rag_turn.kql
./scripts/kql.sh -b workspace -t P2D -o table scripts/kql/dev_recent_turns_and_stops.kql
```

Set `trace_id` in `scripts/kql/turn_latency_by_trace.kql` for one turn timeline.

**Bundled sketches:** `scripts/kql/README.md` — `prod_client_feedback_misroute.kql`, `dev_early_term_24m_audit.kql`, etc.

Parse audit: `message startswith "RAG_TURN_AUDIT "` → JSON after prefix 15 chars.

## Local RAG harness

Requires `.env` with `OPENAI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_NAMESPACE` (usually `v3` for dev).

```bash
./scripts/bot.sh rag --question "…"
./scripts/bot.sh rag --file logs/client_feedback_golden.txt
./scripts/bot.sh probe "…" --top-k 8
```

Output: stdout + `teams-bot/logs/local_rag_run.log`; audits on stderr.

## Regression sweep (after bot or corpus change)

1. `./scripts/bot.sh pytest tests/test_client_feedback_golden.py -q`
2. Spot-check 3–5 golden lines via `bot.sh rag`
3. If user reports prod issue: `kql.sh` on prod App Insights + compare paths to evidence docs
4. Document pass/fail in chat; score against [acceptance-criteria.md](acceptance-criteria.md)

## Multi-turn Teams cases

Use a **fresh thread** unless the case says otherwise. For clarify gate (A9, B4): verify `response_path=clarify` in audit when ambiguous.

## Corpus Q&A export {#corpus-qa-export}

```bash
./scripts/kb.sh qa-export --seed 42
```

Edit `pinecone-pipeline/agent_exports/corpus_qa_for_cursor.md` — answers only from quoted chunks.

Then validate with:

```bash
./scripts/bot.sh rag --file logs/corpus_qa_questions.txt
./scripts/bot.sh probe -f logs/corpus_qa_questions.txt -k 8
```

## Issue classification (investigation)

| Symptom | Likely lane | Next step |
|---------|-------------|-----------|
| Right docs in `retrieved_documents`, wrong answer | GENERATION | Bot prompts/composer |
| Wrong paths in audit | RETRIEVAL | Scope, folder map, probe |
| Empty/wrong facts in CONTEXT | DATA | KB curator |
| No RAG when history enough | Optimizer | `optimizer_reuse_rate.kql` |
