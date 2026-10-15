# Conversation mining (Phase 5 scaffolding)

Offline helpers that turn sample `RAG_TURN_AUDIT` JSON into **candidate process sketches** shaped like [`process-engine`](../process-engine/) definitions. No App Insights, KQL, or Mongo access.

Design: [`docs/office-ide/PROCESS-MINING.md`](../docs/office-ide/PROCESS-MINING.md). Frontend gate (same phase): [`docs/office-ide/FRONTEND-EXIT-CRITERIA.md`](../docs/office-ide/FRONTEND-EXIT-CRITERIA.md).

## Layout

| Path | Role |
|------|------|
| `conversation_mining/audit.py` | Parse audit payload / App Insights log line |
| `conversation_mining/sketch.py` | Cluster turns → candidate `ProcessDefinition`-shaped dicts |
| `fixtures/sample_rag_turn_audits.json` | Synthetic web-channel audits |
| `tests/` | Unit tests (no network) |

## Dry-run

```bash
cd conversation-mining
python -m pytest -q
# or:
python -c "from pathlib import Path; from conversation_mining.sketch import sketches_from_audits, load_audit_fixture; print(sketches_from_audits(load_audit_fixture(Path('fixtures/sample_rag_turn_audits.json'))))"
```

Promotion into the live catalog is **manual** after human review — see PROCESS-MINING.md.
