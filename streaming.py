"""Streaming response support — Claude --output-format stream-json → TG sendMessageDraft.

Flow:
1. Spawn `claude -p --output-format stream-json --include-partial-messages`
2. Parse JSON lines, extract content_block_delta text increments
3. Accumulate text, periodically push to TG via send_message_draft (native streaming UX)
4. Finalize with edit_message_text on completion
5. On long output (>4000 chars), split across multiple messages

Rate limiting:
- TG bot drafts have rate limits. Throttle to max 1 update per second OR every 50 new chars.
- Final edit always sent regardless of throttle.

Fallback:
- If send_message_draft is unavailable (older library or API quirk), fall back to edit_message_text.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Awaitable, Callable

logger = logging.getLogger(__name__)

# Tuning constants
UPDATE_INTERVAL_SEC = 1.0
UPDATE_DELTA_CHARS = 50
TG_MAX_MESSAGE_CHARS = 4000


async def claude_stream(
    cmd: list[str],
    prompt: str,
    cwd: str | None = None,
) -> AsyncGenerator[str, None]:
    """Async generator yielding text deltas from `claude -p --output-format stream-json`.

    Args:
        cmd: Full command list including `--output-format stream-json --include-partial-messages --verbose`.
        prompt: Prompt to send via stdin.
        cwd: Working directory.

    Yields:
        Incremental text strings (deltas) as they arrive.

    Raises:
        RuntimeError: If subprocess exits with non-zero status. Carries stderr.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    # Send prompt and close stdin
    assert proc.stdin is not None
    proc.stdin.write(prompt.encode())
    await proc.stdin.drain()
    proc.stdin.close()

    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        try:
            event = json.loads(line.decode())
        except json.JSONDecodeError:
            # Skip malformed lines (sometimes claude emits non-JSON debug)
            continue

        # Extract incremental text from content_block_delta events
        if event.get("type") == "stream_event":
            ev = event.get("event", {})
            if ev.get("type") == "content_block_delta":
                delta = ev.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        yield text

    await proc.wait()
    if proc.returncode != 0:
        assert proc.stderr is not None
        stderr_bytes = await proc.stderr.read()
        raise RuntimeError(stderr_bytes.decode().strip() or f"claude exited with code {proc.returncode}")


async def stream_to_telegram(
    initial_send: Callable[[str], Awaitable],
    update_message: Callable[[str], Awaitable[bool]],
    text_stream: AsyncGenerator[str, None],
    long_message_split: Callable[[str], Awaitable] | None = None,
) -> str:
    """Consume text stream and push updates to Telegram with rate limiting.

    Args:
        initial_send: Async callable that sends placeholder message and returns the message object.
            Signature: `async def(text: str) -> Message`
        update_message: Async callable that updates an existing message.
            Signature: `async def(text: str) -> bool` — returns True if updated, False if skipped/failed.
        text_stream: Async generator yielding text deltas.
        long_message_split: Optional callable for handling very long outputs (>TG_MAX_MESSAGE_CHARS).
            Signature: `async def(full_text: str) -> None`. If None, just truncates.

    Returns:
        The accumulated final text.
    """
    # Send initial placeholder message
    await initial_send("生成中...")

    accumulated = ""
    last_sent_len = 0
    last_update_time = time.time()

    try:
        async for chunk in text_stream:
            accumulated += chunk
            now = time.time()

            time_elapsed = now - last_update_time
            chars_since_last = len(accumulated) - last_sent_len

            should_update = (
                time_elapsed >= UPDATE_INTERVAL_SEC
                or chars_since_last >= UPDATE_DELTA_CHARS
            )

            if should_update:
                # Truncate if exceeds TG single-message limit (final split happens after stream ends)
                display = accumulated if len(accumulated) <= TG_MAX_MESSAGE_CHARS else accumulated[:TG_MAX_MESSAGE_CHARS] + "\n…"
                ok = await update_message(display)
                if ok:
                    last_update_time = now
                    last_sent_len = len(accumulated)
    except Exception as e:
        # Stream error mid-flight — append marker
        logger.warning(f"Stream interrupted: {e}")
        accumulated += f"\n\n⚠️ 生成中斷：{str(e)[:200]}"

    # Empty output guard
    if not accumulated.strip():
        accumulated = "（無回應）"

    # Final delivery
    if len(accumulated) <= TG_MAX_MESSAGE_CHARS:
        await update_message(accumulated)
    else:
        # Long output: split across multiple messages
        if long_message_split is not None:
            await long_message_split(accumulated)
        else:
            # Just take the first chunk
            await update_message(accumulated[:TG_MAX_MESSAGE_CHARS])

    return accumulated
