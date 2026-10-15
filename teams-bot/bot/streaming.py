"""Teams Streaming API implementation for progressive message delivery."""
import asyncio
import json
import logging
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import aiohttp

from .activity_handler import TeamsActivity
from .turn_latency import current_turn_latency


logger = logging.getLogger(__name__)


@dataclass
class StreamState:
    """Track the state of an active stream."""
    stream_id: Optional[str] = None
    sequence: int = 0
    accumulated_text: str = ""
    """Latest status line for informative activities (single line; replaced on each update)."""
    informative_cumulative: str = ""
    is_active: bool = True
    last_send_time: float = 0


class TeamsStreamer:
    """
    Handle streaming messages to Teams using the Streaming API.
    
    The Teams Streaming API allows sending progressive updates to users:
    1. Informative updates (blue progress bar)
    2. Streaming text (typing indicator with growing text)
    3. Final message (complete response)
    
    Constraints:
    - Only works in 1:1 chats (not group chats)
    - Rate limit: 1 request per second
    - Max streaming time: 2 minutes
    - Each activity's ``text`` must contain the full text from the previous activity in this
      stream (cumulative). Informative updates therefore grow a shared status block; answer
      chunks prepend that block so the main body always extends the last informative.

    Pacing constants (Microsoft Teams streaming UX / Bot Framework channel posting):
    - ``RATE_LIMIT_SECONDS``: Bot channel posting is throttled to about **one POST per second**
      for streaming activities; ``send_informative`` / ``send_chunk`` / ``send_final`` all call
      ``_wait_for_rate_limit`` so we stay under that limit.
    - ``MAX_INFORMATIVE_LENGTH``: Informative ``text`` payloads are capped at **1000 characters**
      (~1 KB) so we stay within typical streaming payload size guidance for status lines.
    - ``STREAMING_MIN_CHARS_BEFORE_FIRST_SEND``: Minimum cumulative answer characters before the
      first non-final streaming chunk (``function_app`` uses the same value for pacing).
    - **HTTP 429** from Bot Framework (``API calls quota exceeded``): ``_send_activity`` retries
      with exponential backoff before failing the turn.
    """

    #: Minimum interval between successive Bot Framework POSTs for this stream (seconds).
    #: Channel guidance is about **one POST per second** for streaming; staying at or
    #: above 1.0s avoids ``429 API calls quota exceeded`` on long answers (informative
    #: + chunk posts share this budget). If UX feels slow, prefer larger text deltas in
    #: the caller rather than lowering this below 1.0.
    RATE_LIMIT_SECONDS = 1.0
    #: Maximum characters for a single informative status line (1 KB cap for status text).
    MAX_INFORMATIVE_LENGTH = 1000
    #: Minimum answer body length before sending the first partial streaming chunk.
    #: Tuned low (~3-5 words) so the user sees text grow about a second after the
    #: model starts emitting tokens, instead of waiting for a full sentence.
    STREAMING_MIN_CHARS_BEFORE_FIRST_SEND = 20
    
    def __init__(
        self,
        activity: TeamsActivity,
        app_id: str,
        app_password: str,
    ):
        self.activity = activity
        self.app_id = app_id
        self.app_password = app_password
        self.state = StreamState()
        self._token: Optional[str] = None
        self._token_expires: float = 0
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
    
    async def _get_token(self) -> str:
        """Get or refresh Bot Framework OAuth token."""
        import os

        if self._token and time.time() < self._token_expires - 60:
            return self._token
        
        tenant_id = os.environ["MICROSOFT_APP_TENANT_ID"]
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        
        data = {
            "grant_type": "client_credentials",
            "client_id": self.app_id,
            "client_secret": self.app_password,
            "scope": "https://api.botframework.com/.default",
        }
        
        async with self._session.post(token_url, data=data) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"Failed to get token: {response.status} - {error_text}")
            
            result = await response.json()
            self._token = result["access_token"]
            self._token_expires = time.time() + result.get("expires_in", 3600)
            return self._token
    
    #: Retries when Bot Framework returns HTTP 429 (streaming channel quota).
    _BOT_FRAMEWORK_429_MAX_ATTEMPTS = 6

    async def _send_activity(self, activity: dict, *, latency_case: str) -> dict:
        """Send an activity to the conversation."""
        token = await self._get_token()

        service_url = self.activity.service_url.rstrip("/")
        conversation_id = urllib.parse.quote(self.activity.conversation_id)
        url = f"{service_url}/v3/conversations/{conversation_id}/activities"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        outbound_text = activity.get("text") or ""
        preview = outbound_text[:120]

        attempt = 0
        while True:
            attempt += 1
            http_started = time.perf_counter()

            async with self._session.post(url, json=activity, headers=headers) as response:
                if response.status in (200, 201, 202):
                    result: dict = {}
                    try:
                        body = await response.text()
                        if body and body.strip():
                            result = json.loads(body)
                            logger.debug(f"Response {response.status}: {result}")
                    except Exception as exc:
                        logger.debug(f"Could not parse response body: {exc}")

                    http_ms = (time.perf_counter() - http_started) * 1000
                    latency = current_turn_latency()
                    if latency:
                        stream_entity: dict = {}
                        entities = activity.get("entities") or []
                        if entities and isinstance(entities[0], dict):
                            stream_entity = entities[0]
                        latency.emit(
                            "teams_botframework_post",
                            outbound_case=latency_case,
                            http_ms=round(http_ms, 2),
                            http_status=response.status,
                            text_chars=len(outbound_text),
                            text_preview=preview,
                            ok=True,
                            activity_type=activity.get("type"),
                            stream_type=stream_entity.get("streamType"),
                            stream_sequence=stream_entity.get("streamSequence"),
                        )
                    return result

                error_text = await response.text()
                http_ms = (time.perf_counter() - http_started) * 1000
                latency = current_turn_latency()
                if latency:
                    latency.emit(
                        "teams_botframework_post",
                        outbound_case=latency_case,
                        http_ms=round(http_ms, 2),
                        http_status=response.status,
                        text_chars=len(outbound_text),
                        text_preview=preview,
                        ok=False,
                        error_preview=error_text[:200],
                    )

                if response.status == 429 and attempt < self._BOT_FRAMEWORK_429_MAX_ATTEMPTS:
                    backoff_seconds = min(8.0, 1.0 * (2 ** (attempt - 1)))
                    logger.warning(
                        "Bot Framework 429 (quota); backing off %.1fs then retry %s/%s: %s",
                        backoff_seconds,
                        attempt,
                        self._BOT_FRAMEWORK_429_MAX_ATTEMPTS,
                        error_text[:180],
                    )
                    await asyncio.sleep(backoff_seconds)
                    self.state.last_send_time = time.time()
                    continue

                logger.error(f"Failed to send activity: {response.status} - {error_text}")

                if response.status == 403:
                    error_code = _parse_botframework_error_code(error_text)
                    # Bot Framework reuses 403 for two very different cases:
                    # - User-stopped stream → genuine cancellation; abort the turn.
                    # - ContentStreamNotAllowed → the streamed text was not a strict
                    #   prefix-extension of the previous chunk; the stream is unusable but
                    #   the answer still needs to be delivered (caller falls back to a
                    #   plain non-streaming message).
                    if error_code == "ContentStreamNotAllowed":
                        self.state.is_active = False
                        raise StreamingProtocolError(error_text)
                    self.state.is_active = False
                    raise StreamingStoppedError("User stopped the stream")

                raise RuntimeError(f"Failed to send activity: {response.status} - {error_text}")
    
    async def _wait_for_rate_limit(self):
        """Wait if needed to respect rate limits."""

        elapsed = time.time() - self.state.last_send_time
        if elapsed < self.RATE_LIMIT_SECONDS:
            await asyncio.sleep(self.RATE_LIMIT_SECONDS - elapsed)
        
        self.state.last_send_time = time.time()
    
    def _build_streaming_activity(
        self,
        text: str,
        stream_type: str,
        is_final: bool = False,
    ) -> dict:
        """Build a streaming activity following Teams Streaming API format."""
        self.state.sequence += 1
        
        # Build activity with all required fields per documentation
        activity = {
            "type": "message" if is_final else "typing",
            "serviceUrl": self.activity.service_url,
            "channelId": self.activity.channel_id,
            "from": self.activity.raw_activity.get("recipient"),
            "recipient": self.activity.raw_activity.get("from"),
            "conversation": self.activity.raw_activity.get("conversation"),
            "locale": self.activity.raw_activity.get("locale", "en-US"),
            "text": text,
            "entities": [
                {
                    "type": "streaminfo",
                    "streamType": stream_type,
                }
            ],
        }
        # Teams renders markdown links in citations only when the activity declares markdown.
        if is_final:
            activity["textFormat"] = "markdown"
        
        # Add stream ID for continuation (required after first message)
        if self.state.stream_id:
            activity["entities"][0]["streamId"] = self.state.stream_id
        
        # Add sequence number (required for non-final messages)
        if not is_final:
            activity["entities"][0]["streamSequence"] = self.state.sequence
        
        return activity

    def _effective_stream_text(self, answer_body: str) -> str:
        """
        Return the answer body only for streaming/final message text.

        Status lines are sent only as separate **informative** activities so the user does not
        see a wall of processing steps prepended to the assistant reply. (Informative updates
        still participate in the same stream for Teams.)
        """
        return answer_body.strip()

    async def send_informative(self, message: str, *, latency_case: str = "informative") -> None:
        """
        Send an informative update (blue progress bar).

        Args:
            message: Status message like "Przeszukuję dokumenty..."
            latency_case: Label for latency logs (what triggered this send).
        """
        if not self.state.is_active:
            return
        
        if self.activity.is_group_chat:
            logger.warning("Streaming not supported in group chats, skipping informative")
            return

        msg = message.strip()
        if not msg:
            return

        # Replace (do not append): show only the current step in Teams. Prefix for answer
        # chunks still uses this single line so cumulative content stays consistent.
        self.state.informative_cumulative = msg
        if len(self.state.informative_cumulative) > self.MAX_INFORMATIVE_LENGTH:
            self.state.informative_cumulative = (
                self.state.informative_cumulative[: self.MAX_INFORMATIVE_LENGTH - 1] + "…"
            )

        text_to_send = self.state.informative_cumulative

        await self._wait_for_rate_limit()

        activity = self._build_streaming_activity(text_to_send, "informative")

        try:
            result = await self._send_activity(activity, latency_case=latency_case)
            logger.info(f"Informative response: {result}")
            
            # Store stream ID from first response (201 Created returns {"id": "..."})
            if not self.state.stream_id and "id" in result:
                self.state.stream_id = result["id"]
                logger.info(f"Started stream with ID: {self.state.stream_id}")
            elif not self.state.stream_id:
                logger.warning("No stream ID in response - streaming chunks may fail")
                
        except StreamingStoppedError:
            logger.info("User stopped streaming during informative update")
            raise
    
    async def send_chunk(
        self,
        accumulated_text: str,
        *,
        latency_case: str = "streaming_chunk",
    ) -> None:
        """
        Send a streaming text chunk.

        IMPORTANT: The text must be cumulative - include all previous text!

        Args:
            accumulated_text: All text generated so far (not just the new part)
            latency_case: Label for latency logs.
        """
        if not self.state.is_active:
            return
        
        if self.activity.is_group_chat:
            # For group chats, just update internal state
            self.state.accumulated_text = accumulated_text
            return
        
        # Stream ID is required for streaming chunks
        if not self.state.stream_id:
            logger.warning("No stream ID available, skipping chunk")
            self.state.accumulated_text = accumulated_text
            return
        
        # Skip empty chunks - Teams requires text in streaming activities
        if not accumulated_text or not accumulated_text.strip():
            logger.debug("Skipping empty chunk")
            return
        
        await self._wait_for_rate_limit()

        self.state.accumulated_text = accumulated_text
        display_text = self._effective_stream_text(accumulated_text)
        activity = self._build_streaming_activity(display_text, "streaming")

        try:
            result = await self._send_activity(activity, latency_case=latency_case)
            # Capture stream ID from any response that has it
            if not self.state.stream_id and "id" in result:
                self.state.stream_id = result["id"]
        except StreamingStoppedError:
            logger.info("User stopped streaming")
            raise
    
    async def send_final(
        self,
        text: str,
        sources: Optional[list[dict]] = None,
        *,
        latency_case: str = "final_message",
    ) -> None:
        """
        Send the final message with complete response.

        Args:
            text: Complete response text
            sources: Optional list of source documents for citations
            latency_case: Label for latency logs.
        """
        # If no stream ID, fall back to regular message
        if self.activity.is_group_chat or not self.state.stream_id:
            if not self.state.stream_id and not self.activity.is_group_chat:
                logger.warning("No stream ID for final message, sending as regular message")
            # Send as regular message
            activity = {
                "type": "message",
                "text": text,
                "textFormat": "markdown",
                "from": self.activity.raw_activity.get("recipient"),
                "recipient": self.activity.raw_activity.get("from"),
                "conversation": self.activity.raw_activity.get("conversation"),
            }
        else:
            # For 1:1 chats with stream ID, send as final streaming message
            activity = self._build_streaming_activity(
                self._effective_stream_text(text), "final", is_final=True
            )
        
        # Add AI-generated label
        if "entities" not in activity:
            activity["entities"] = []
        
        activity["entities"].append({
            "type": "https://schema.org/Message",
            "@type": "Message",
            "@context": "https://schema.org",
            "additionalType": ["AIGeneratedContent"],
        })

        await self._send_activity(activity, latency_case=latency_case)
        self.state.is_active = False
        logger.info("Sent final message, stream complete")

    async def send_message(self, text: str, *, latency_case: str) -> None:
        """
        Post a standalone non-streaming message activity (one Teams bubble).

        Independent of any active stream — this is the building block for delivering an
        answer as several paragraph-sized bubbles instead of one giant streamed bubble.
        Honours the same per-conversation rate limit as streaming activities so we do
        not get throttled when shipping 4–6 messages back-to-back.
        """
        body = (text or "").strip()
        if not body:
            return

        await self._wait_for_rate_limit()

        activity = {
            "type": "message",
            "text": body,
            "textFormat": "markdown",
            "from": self.activity.raw_activity.get("recipient"),
            "recipient": self.activity.raw_activity.get("from"),
            "conversation": self.activity.raw_activity.get("conversation"),
            "entities": [
                {
                    "type": "https://schema.org/Message",
                    "@type": "Message",
                    "@context": "https://schema.org",
                    "additionalType": ["AIGeneratedContent"],
                }
            ],
        }
        await self._send_activity(activity, latency_case=latency_case)

    async def delete_stream_activity(self) -> bool:
        """Delete the partial streaming bubble via Bot Framework REST DELETE.

        Used to recover from ``ContentStreamNotAllowed`` mid-stream: after Teams rejects
        a chunk (or final), the bubble is left visible at whatever the last successful
        chunk shipped (e.g. ``"...po czym decydu"`` truncated mid-word). Deleting it
        before sending the authoritative answer as a fresh ``send_message`` keeps the
        user from seeing both the broken partial and the clean answer at the same time.

        Returns ``True`` when Teams confirms the delete (200/202/204), ``False`` on any
        other status or transport error. The caller should treat ``False`` as
        best-effort failure: still ship the fallback message so the user gets the
        answer, even if the partial bubble lingers.

        No-op (returns ``False``) when there is no active stream id (e.g. group chats,
        or when the very first informative POST itself failed).
        """
        if not self.state.stream_id:
            return False
        if self.activity.is_group_chat:
            return False

        token = await self._get_token()
        service_url = self.activity.service_url.rstrip("/")
        conv_id = urllib.parse.quote(self.activity.conversation_id)
        activity_id = urllib.parse.quote(self.state.stream_id)
        url = f"{service_url}/v3/conversations/{conv_id}/activities/{activity_id}"

        headers = {"Authorization": f"Bearer {token}"}
        http_started = time.perf_counter()
        try:
            async with self._session.delete(url, headers=headers) as response:
                http_ms = (time.perf_counter() - http_started) * 1000
                ok = response.status in (200, 202, 204)
                error_preview = "" if ok else (await response.text())[:200]
                latency = current_turn_latency()
                if latency:
                    latency.emit(
                        "teams_botframework_delete",
                        outbound_case="delete_partial_stream_bubble",
                        http_ms=round(http_ms, 2),
                        http_status=response.status,
                        ok=ok,
                        error_preview=error_preview,
                    )
                if ok:
                    self.state.is_active = False
                    logger.info(
                        "Deleted partial stream activity %s (status=%s)",
                        self.state.stream_id, response.status,
                    )
                else:
                    logger.warning(
                        "Failed to delete partial stream activity %s: %s %s",
                        self.state.stream_id, response.status, error_preview,
                    )
                return ok
        except Exception as exc:
            logger.warning("delete_stream_activity raised: %s", exc)
            latency = current_turn_latency()
            if latency:
                latency.emit(
                    "teams_botframework_delete",
                    outbound_case="delete_partial_stream_bubble",
                    ok=False,
                    error_preview=str(exc)[:200],
                )
            return False

    async def send_typing(self, *, latency_case: str = "typing_indicator") -> None:
        """
        Post a transient ``type=typing`` activity (built-in Teams indicator, no text).

        Useful between paragraph messages so the user sees that more content is coming.
        Group chats fall through silently.
        """
        if self.activity.is_group_chat:
            return
        activity = {
            "type": "typing",
            "from": self.activity.raw_activity.get("recipient"),
            "recipient": self.activity.raw_activity.get("from"),
            "conversation": self.activity.raw_activity.get("conversation"),
        }
        try:
            await self._send_activity(activity, latency_case=latency_case)
        except StreamingProtocolError:
            return
        except StreamingStoppedError:
            raise


class StreamingStoppedError(Exception):
    """Raised when the user stops the streaming response."""
    pass


class StreamingProtocolError(Exception):
    """
    Raised when Teams rejects a streaming activity for a protocol reason that is **not** a user
    cancellation (e.g. ``ContentStreamNotAllowed`` when a chunk does not strictly extend the
    previously streamed text). Callers should treat this as "stream is dead, deliver the answer
    via plain non-streaming messages instead".
    """
    pass


def _parse_botframework_error_code(error_text: str) -> str:
    """Return the ``error.code`` field from a Bot Framework error JSON body, or ``""``."""
    try:
        body = json.loads(error_text or "")
    except (ValueError, TypeError):
        return ""
    error_obj = body.get("error") if isinstance(body, dict) else None
    if isinstance(error_obj, dict):
        code = error_obj.get("code")
        if isinstance(code, str):
            return code
    return ""
