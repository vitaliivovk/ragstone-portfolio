"""Azure Table Storage cache of last retrieved RAG chunks per user (reuse / augment turns)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from azure.core.exceptions import ResourceExistsError
from azure.data.tables.aio import TableClient, TableServiceClient


logger = logging.getLogger(__name__)


class ContextCache:
    """
    One row per RAG turn with retrieval: formatted context, sources metadata, Pinecone chunk ids.

    PartitionKey = user_id (same as conversation memory). RowKey = inverted timestamp (newest
    has lexicographically smallest RowKey when using the same scheme as ``TableStorageMemory``).
    """

    TABLE_NAME = "conversationcontext"

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._table_created = False

    def _inverted_timestamp_row_key(self) -> str:
        max_ticks = 9999999999999999
        now = datetime.now(timezone.utc)
        current_ticks = int(now.timestamp() * 1000000)
        inverted = max_ticks - current_ticks
        return f"{inverted:019d}"

    async def _ensure_table_exists(self, table: TableClient) -> None:
        if self._table_created:
            return
        try:
            await table.create_table()
            logger.info("Created table: %s", self.TABLE_NAME)
        except ResourceExistsError:
            pass
        self._table_created = True

    async def save(
        self,
        user_id: str,
        *,
        optimized_query: str,
        context_text: str,
        sources: list[dict[str, Any]],
        chunk_ids: list[str],
        conversation_id: str = "",
    ) -> None:
        """Persist retrieval outcome for possible reuse on the next turn."""
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table_exists(table)
            entity: dict[str, Any] = {
                "PartitionKey": user_id,
                "RowKey": self._inverted_timestamp_row_key(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "optimized_query": (optimized_query or "")[:4000],
                "context_text": context_text or "",
                "sources_json": json.dumps(sources, ensure_ascii=False)[:60000],
                "chunk_ids_json": json.dumps(chunk_ids, ensure_ascii=False)[:60000],
                "conversation_id": (conversation_id or "")[:1024],
            }
            await table.upsert_entity(entity)
            logger.debug("Saved context cache row for user %s", user_id)

    async def get_latest(
        self,
        user_id: str,
        *,
        conversation_id: str = "",
    ) -> Optional[dict[str, Any]]:
        """
        Return the newest cached retrieval row for ``user_id``, or None.

        When ``conversation_id`` is given (non-empty), only rows whose stored
        ``conversation_id`` matches are considered — protects the optimizer
        from reusing context that came from an unrelated chat thread the same
        user happens to have open. When empty, falls back to legacy behaviour
        (newest row regardless of conversation).

        Keys: ``context_text``, ``sources`` (list[dict]), ``chunk_ids`` (list[str]),
        ``optimized_query``, ``timestamp``, ``conversation_id``.
        """
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table_exists(table)
            query_filter = f"PartitionKey eq '{_escape_odata_string(user_id)}'"
            if conversation_id:
                escaped_conv = _escape_odata_string(conversation_id)
                query_filter = (
                    f"{query_filter} and conversation_id eq '{escaped_conv}'"
                )
            best_row_key: Optional[str] = None
            best_entity: Optional[dict[str, Any]] = None
            async for entity in table.query_entities(
                query_filter=query_filter,
                select=[
                    "RowKey",
                    "timestamp",
                    "optimized_query",
                    "context_text",
                    "sources_json",
                    "chunk_ids_json",
                    "conversation_id",
                ],
            ):
                row_key = str(entity["RowKey"])
                if best_row_key is None or row_key < best_row_key:
                    best_row_key = row_key
                    best_entity = dict(entity)
            if best_entity is None:
                return None
            sources_raw = best_entity.get("sources_json") or "[]"
            chunk_raw = best_entity.get("chunk_ids_json") or "[]"
            try:
                sources = json.loads(sources_raw)
            except json.JSONDecodeError:
                sources = []
            try:
                chunk_ids = json.loads(chunk_raw)
            except json.JSONDecodeError:
                chunk_ids = []
            if not isinstance(sources, list):
                sources = []
            if not isinstance(chunk_ids, list):
                chunk_ids = []
            return {
                "context_text": str(best_entity.get("context_text") or ""),
                "sources": sources,
                "chunk_ids": [str(chunk_id) for chunk_id in chunk_ids],
                "optimized_query": str(best_entity.get("optimized_query") or ""),
                "timestamp": str(best_entity.get("timestamp") or ""),
                "conversation_id": str(best_entity.get("conversation_id") or ""),
            }

    async def purge_older_than_hours(self, hours: float) -> int:
        """Delete cache rows whose ``timestamp`` is older than ``hours`` (UTC). Returns delete count."""
        if hours <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()
        deleted = 0
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table_exists(table)
            query_filter = f"timestamp lt '{_escape_odata_string(cutoff_iso)}'"
            async for entity in table.query_entities(
                query_filter=query_filter,
                select=["PartitionKey", "RowKey"],
            ):
                await table.delete_entity(
                    partition_key=entity["PartitionKey"],
                    row_key=entity["RowKey"],
                )
                deleted += 1
        if deleted:
            logger.info("Context cache purge removed %s rows (older than %s h)", deleted, hours)
        return deleted

    async def clear_user_context(self, user_id: str) -> int:
        """
        Delete all context-cache rows for ``user_id`` (same partition as conversation memory).

        Used when the user resets chat history so the optimizer does not reuse stale retrieval.
        """
        deleted = 0
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table_exists(table)
            query_filter = f"PartitionKey eq '{_escape_odata_string(user_id)}'"
            async for entity in table.query_entities(
                query_filter=query_filter,
                select=["PartitionKey", "RowKey"],
            ):
                await table.delete_entity(
                    partition_key=entity["PartitionKey"],
                    row_key=entity["RowKey"],
                )
                deleted += 1
        if deleted:
            logger.info("Cleared %s context-cache rows for user %s", deleted, user_id)
        return deleted


def _escape_odata_string(value: str) -> str:
    """Escape single quotes for Azure Table OData filters."""
    return value.replace("'", "''")
