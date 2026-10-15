"""One-shot Bot Framework OAuth token fetch (used for cold-start pre-warm)."""

from __future__ import annotations

import logging
import os
import time

import aiohttp

logger = logging.getLogger(__name__)


async def prefetch_bot_framework_token(
    *,
    app_id: str,
    app_password: str,
) -> None:
    """
    Acquire a client-credentials token for ``https://api.botframework.com/.default``.

    Discards the token; purpose is to warm DNS/TLS and token endpoint before the first
    Teams streaming POST.
    """
    tenant_id = os.environ["MICROSOFT_APP_TENANT_ID"]
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": app_id,
        "client_secret": app_password,
        "scope": "https://api.botframework.com/.default",
    }
    http_started = time.perf_counter()
    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, data=data) as response:
            body_preview = (await response.text())[:200]
            http_ms = (time.perf_counter() - http_started) * 1000
            if response.status != 200:
                logger.warning(
                    "Prewarm Bot Framework token failed: status=%s http_ms=%.0f body=%r",
                    response.status,
                    http_ms,
                    body_preview,
                )
                return
            logger.info(
                "Prewarm Bot Framework token ok: http_ms=%.0f",
                http_ms,
            )
