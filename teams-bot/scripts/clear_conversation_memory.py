#!/usr/bin/env python3
"""
Delete conversation rows from Azure Table Storage (teams-bot memory).

Uses the same connection string as the Function App:
  AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage

Examples (from teams-bot directory):
  python scripts/clear_conversation_memory.py --user-id "29:1abc..." --yes
  python scripts/clear_conversation_memory.py --all --yes
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

_TEAMS_BOT_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _TEAMS_BOT_ROOT.parent

if str(_TEAMS_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEAMS_BOT_ROOT))

load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_TEAMS_BOT_ROOT / ".env")

from config import load_rag_stack_settings
from rag.memory import TableStorageMemory


async def _run(*, user_id: str | None, clear_all: bool) -> int:
    _openai, _pinecone, storage_cfg = load_rag_stack_settings()
    storage_cs = storage_cfg.connection_string or ""
    if not storage_cs.strip():
        print(
            "ERROR: Set AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage.",
            file=sys.stderr,
        )
        return 2

    memory = TableStorageMemory(storage_cs.strip())
    if clear_all:
        deleted = await memory.clear_all_history()
        print(f"Deleted {deleted} row(s) from table '{TableStorageMemory.TABLE_NAME}'.")
        return 0

    deleted = await memory.clear_history(user_id)
    print(
        f"Deleted {deleted} row(s) for PartitionKey={user_id!r} "
        f"in table '{TableStorageMemory.TABLE_NAME}'."
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--user-id",
        metavar="PARTITION_KEY",
        help="Teams user id (Table PartitionKey) to wipe",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Delete every row in the conversations table",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation (refuse without it)",
    )
    args = parser.parse_args()

    if not args.yes:
        print("ERROR: Refusing to delete without --yes.", file=sys.stderr)
        sys.exit(2)

    user_id: str | None = args.user_id if args.user_id else None
    clear_all: bool = bool(args.all)

    exit_code = asyncio.run(_run(user_id=user_id, clear_all=clear_all))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
