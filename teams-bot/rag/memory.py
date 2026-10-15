"""Azure Table Storage conversation memory for persistent chat history."""
import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Optional

from azure.core.exceptions import ResourceExistsError
from azure.data.tables.aio import TableClient, TableServiceClient
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


logger = logging.getLogger(__name__)


def _apply_message_limit(messages: list[BaseMessage], limit: int) -> list[BaseMessage]:
    if limit < 0:
        return messages
    if limit == 0:
        return []
    if len(messages) > limit:
        return messages[-limit:]
    return messages


class TableStorageMemory:
    """
    Fast conversation memory using Azure Table Storage.

    Uses PartitionKey = user_id for per-user isolation.
    Uses RowKey = inverted timestamp for natural ordering (newest first in storage,
    but we reverse when returning to get chronological order).

    Performance:
    - Read: ~20ms for last 10 messages
    - Write: ~10ms per message pair

    Optional in-process TTL+LRU cache (see ``history_cache_ttl_seconds``): reduces repeated
    Table reads within a short window for the same user.
    """

    TABLE_NAME = "conversations"

    def __init__(
        self,
        connection_string: str,
        *,
        history_cache_ttl_seconds: float = 30.0,
        history_cache_max_users: int = 256,
    ):
        """
        Initialize the memory store.

        Args:
            connection_string: Azure Storage Account connection string
            history_cache_ttl_seconds: TTL for cached full history per user; ``0`` disables cache
            history_cache_max_users: Max distinct users kept in the in-process cache
        """
        self.connection_string = connection_string
        self._table_created = False
        self._history_cache_ttl_seconds = float(history_cache_ttl_seconds)
        self._history_cache_max_users = int(history_cache_max_users)
        self._history_cache: OrderedDict[str, tuple[list[BaseMessage], float]] = OrderedDict()
        self._history_cache_lock = asyncio.Lock()

    def _get_inverted_timestamp(self) -> str:
        """
        Generate an inverted timestamp for RowKey ordering.

        Azure Table Storage sorts RowKey ascending, so we use
        (max_ticks - current_ticks) to get newest-first ordering.
        """
        max_ticks = 9999999999999999
        now = datetime.now(timezone.utc)
        current_ticks = int(now.timestamp() * 1000000)
        inverted = max_ticks - current_ticks
        return f"{inverted:019d}"

    async def _ensure_table_exists(self, table_client: TableClient) -> None:
        """Create the table if it doesn't exist."""
        if self._table_created:
            return

        try:
            await table_client.create_table()
            logger.info("Created table: %s", self.TABLE_NAME)
        except ResourceExistsError:
            pass  # Table already exists

        self._table_created = True

    def _invalidate_history_cache(self, user_id: str) -> None:
        self._history_cache.pop(user_id, None)

    async def _load_all_messages_chronological(self, user_id: str) -> list[BaseMessage]:
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table_exists(table)

            messages: list[BaseMessage] = []
            query_filter = f"PartitionKey eq '{user_id}'"

            async for entity in table.query_entities(
                query_filter=query_filter,
                select=["role", "content", "RowKey"],
            ):
                role = entity["role"]
                content = entity["content"]

                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

            messages.reverse()
            return messages

    async def get_history(
        self,
        user_id: str,
        limit: int = 10,
        *,
        on_cache_miss: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> list[BaseMessage]:
        """
        Retrieve the last N messages for a user.

        Args:
            user_id: Teams user ID (PartitionKey)
            limit: Maximum number of messages to return; ``-1`` means return all loaded messages
            on_cache_miss: Called once when a full-history load from Table Storage is required
                (cache disabled, expired, or cold miss)

        Returns:
            List of messages in chronological order (oldest first)
        """
        use_cache = self._history_cache_ttl_seconds > 0.0

        if use_cache:
            async with self._history_cache_lock:
                entry = self._history_cache.get(user_id)
                if entry is not None:
                    cached_messages, expires_at = entry
                    if time.monotonic() < expires_at:
                        self._history_cache.move_to_end(user_id)
                        return _apply_message_limit(list(cached_messages), limit)

        if on_cache_miss is not None:
            await on_cache_miss()

        messages = await self._load_all_messages_chronological(user_id)

        if use_cache:
            expires_at = time.monotonic() + self._history_cache_ttl_seconds
            async with self._history_cache_lock:
                self._history_cache[user_id] = (list(messages), expires_at)
                self._history_cache.move_to_end(user_id)
                while len(self._history_cache) > self._history_cache_max_users:
                    self._history_cache.popitem(last=False)

        return _apply_message_limit(messages, limit)

    async def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
    ) -> None:
        """
        Save a single message to storage.

        Args:
            user_id: Teams user ID (PartitionKey)
            role: "user" or "assistant"
            content: Message content
        """
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table_exists(table)

            entity = {
                "PartitionKey": user_id,
                "RowKey": self._get_inverted_timestamp(),
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await table.upsert_entity(entity)
            logger.debug("Saved %s message for user %s", role, user_id)

    async def save_conversation_turn(
        self,
        user_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """
        Save both user and assistant messages for a conversation turn.

        Args:
            user_id: Teams user ID
            user_message: The user's message
            assistant_message: The assistant's response
        """
        await self.save_message(user_id, "user", user_message)
        await self.save_message(user_id, "assistant", assistant_message)
        self._invalidate_history_cache(user_id)
        logger.info("Saved conversation turn for user %s", user_id)

    async def clear_history(self, user_id: str) -> int:
        """
        Clear all conversation history for a user.

        Args:
            user_id: Teams user ID

        Returns:
            Number of messages deleted
        """
        self._invalidate_history_cache(user_id)
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table_exists(table)

            deleted = 0
            query_filter = f"PartitionKey eq '{user_id}'"

            async for entity in table.query_entities(
                query_filter=query_filter,
                select=["PartitionKey", "RowKey"],
            ):
                await table.delete_entity(
                    partition_key=entity["PartitionKey"],
                    row_key=entity["RowKey"],
                )
                deleted += 1

            logger.info("Cleared %s messages for user %s", deleted, user_id)
            return deleted

    async def clear_all_history(self) -> int:
        """
        Delete every entity in the conversations table (all users).

        Returns:
            Number of rows deleted
        """
        self._history_cache.clear()
        deleted = 0
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table_exists(table)

            async for entity in table.query_entities(
                query_filter="RowKey ne ''",
                select=["PartitionKey", "RowKey"],
            ):
                await table.delete_entity(
                    partition_key=entity["PartitionKey"],
                    row_key=entity["RowKey"],
                )
                deleted += 1

        logger.info("Cleared entire conversations table (%s rows)", deleted)
        return deleted

    async def purge_messages_older_than_hours(self, hours: float) -> int:
        """
        Delete conversation rows whose ``timestamp`` property is older than ``hours`` (UTC).

        Returns the number of deleted entities. ``hours <= 0`` disables deletion (returns 0).
        """
        if hours <= 0:
            return 0
        self._history_cache.clear()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat().replace("'", "''")
        deleted = 0
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table_exists(table)
            query_filter = f"timestamp lt '{cutoff_iso}'"
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
            logger.info(
                "Conversation history purge removed %s rows (older than %s h)",
                deleted,
                hours,
            )
        return deleted
