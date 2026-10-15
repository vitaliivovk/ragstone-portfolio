"""CLI: dry-run a catalog process with mock callouts."""

from __future__ import annotations

import argparse
import json
import sys


def _configure_stdout() -> None:
    """Best-effort UTF-8 for Polish draft bodies on Windows consoles."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


from process_engine.catalog import ProcessCatalog, ProcessNotFound
from process_engine.runner import dry_run


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(
        description="Dry-run a process-engine catalog entry (mocked RAG/plugin/LLM)."
    )
    parser.add_argument(
        "process_id",
        nargs="?",
        default="standard_client_reply",
        help="Process id (default: standard_client_reply)",
    )
    parser.add_argument("--version", default=None, help="Pin version; default = latest")
    parser.add_argument(
        "--catalog",
        default=None,
        help="Catalog root directory (default: bundled process_engine/catalog)",
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Process input (repeatable)",
    )
    parser.add_argument(
        "--inputs-json",
        default=None,
        help="JSON object of inputs (merged with --input)",
    )
    args = parser.parse_args(argv)

    inputs: dict = {}
    if args.inputs_json:
        loaded = json.loads(args.inputs_json)
        if not isinstance(loaded, dict):
            print("--inputs-json must be an object", file=sys.stderr)
            return 2
        inputs.update(loaded)
    for item in args.input:
        if "=" not in item:
            print(f"invalid --input {item!r}; expected KEY=VALUE", file=sys.stderr)
            return 2
        key, value = item.split("=", 1)
        inputs[key] = value

    # Sensible demo defaults for the example process.
    if args.process_id == "standard_client_reply":
        inputs.setdefault("client_name", "Acme Sp. z o.o.")
        inputs.setdefault("client_email", "kontakt@acme.example")
        inputs.setdefault("topic", "procedura kaucji")
        inputs.setdefault("question", "Jak wygląda zwrot kaucji po zakończeniu najmu?")

    catalog = ProcessCatalog(args.catalog)
    try:
        definition = catalog.get(args.process_id, args.version)
    except ProcessNotFound as exc:
        print(f"Process not found: {exc}", file=sys.stderr)
        print(f"Available: {', '.join(catalog.keys()) or '(empty)'}", file=sys.stderr)
        return 1

    result = dry_run(definition, inputs)
    payload = {
        "ok": result.ok,
        "process_id": result.process_id,
        "version": result.version,
        "artifact": result.artifact,
        "steps": [
            {"step_id": t.step_id, "step_type": t.step_type, "output": t.output}
            for t in result.steps
        ],
        "error": result.error,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
