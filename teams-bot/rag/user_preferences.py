"""Per-user answer-style preferences (Azure Table Storage), e.g. set via /style in Teams."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import OrderedDict

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables.aio import TableClient, TableServiceClient

logger = logging.getLogger(__name__)


def _max_preference_chars() -> int:
    raw = os.environ.get("USER_PREFERENCES_MAX_CHARS", "2000").strip()
    parsed = int(raw) if raw else 2000
    return max(256, min(parsed, 8000))


def format_user_preferences_prompt_block(raw: str | None) -> str:
    """Return text injected into the answer system prompt, or empty string."""
    text = (raw or "").strip()
    if not text:
        return ""
    # Framed so the model does not treat /style text as optional flavor text.
    return (
        "**Treść preferencji użytkownika (/style) — zastosuj w tej turze:**\n"
        f"{text}\n"
    )


class UserPreferencesStore:
    """
    One preference string per Teams user (PartitionKey = user id, RowKey = ``style``).

    Uses the same Storage connection string as conversation memory.
    """

    TABLE_NAME = "userpreferences"
    ROW_KEY_STYLE = "style"

    def __init__(
        self,
        connection_string: str,
        *,
        cache_ttl_seconds: float = 30.0,
        cache_max_users: int = 256,
    ):
        self.connection_string = connection_string
        self._table_created = False
        self._cache_ttl_seconds = float(cache_ttl_seconds)
        self._cache_max_users = int(cache_max_users)
        self._cache: OrderedDict[str, tuple[str | None, float]] = OrderedDict()
        self._cache_lock = asyncio.Lock()

    async def _ensure_table(self, table: TableClient) -> None:
        if self._table_created:
            return
        try:
            await table.create_table()
            logger.info("Created table: %s", self.TABLE_NAME)
        except ResourceExistsError:
            pass
        self._table_created = True

    def _invalidate_cache(self, user_id: str) -> None:
        self._cache.pop(user_id, None)

    async def get_text(self, user_id: str) -> str | None:
        """Return stored preference text or None."""
        if self._cache_ttl_seconds > 0.0:
            async with self._cache_lock:
                entry = self._cache.get(user_id)
                if entry is not None:
                    text_cached, expires_at = entry
                    if time.monotonic() < expires_at:
                        self._cache.move_to_end(user_id)
                        return text_cached

        text: str | None = None
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table(table)
            try:
                entity = await table.get_entity(
                    partition_key=user_id,
                    row_key=self.ROW_KEY_STYLE,
                )
            except ResourceNotFoundError:
                text = None
            else:
                raw = entity.get("preferenceText")
                text = str(raw).strip() if raw else None

        if self._cache_ttl_seconds > 0.0:
            expires_at = time.monotonic() + self._cache_ttl_seconds
            async with self._cache_lock:
                self._cache[user_id] = (text, expires_at)
                self._cache.move_to_end(user_id)
                while len(self._cache) > self._cache_max_users:
                    self._cache.popitem(last=False)

        return text

    async def set_text(self, user_id: str, preference_text: str) -> str:
        """Persist trimmed preference text (length-capped). Returns stored value."""
        max_chars = _max_preference_chars()
        trimmed = preference_text.strip()
        if len(trimmed) > max_chars:
            trimmed = trimmed[:max_chars]

        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table(table)
            entity = {
                "PartitionKey": user_id,
                "RowKey": self.ROW_KEY_STYLE,
                "preferenceText": trimmed,
            }
            await table.upsert_entity(entity)

        self._invalidate_cache(user_id)
        logger.info("Updated user preferences for user_id prefix=%s", user_id[:8])
        return trimmed

    async def clear(self, user_id: str) -> None:
        async with TableServiceClient.from_connection_string(
            self.connection_string
        ) as service:
            table = service.get_table_client(self.TABLE_NAME)
            await self._ensure_table(table)
            try:
                await table.delete_entity(
                    partition_key=user_id,
                    row_key=self.ROW_KEY_STYLE,
                )
            except ResourceNotFoundError:
                pass
        self._invalidate_cache(user_id)
        logger.info("Cleared user preferences for user_id prefix=%s", user_id[:8])
