"""Streaming response support — Claude --output-format stream-json → TG sendMessageDraft.

Flow:
1. Spawn `claude -p --output-format stream-json --include-partial-messages`
2. Parse JSON lines, extract content_block_delta text increments
3. Accumulate text; first chunk fires update immediately, then throttled mid-stream updates
4. Finalize with is_final=True so caller can commit the draft as a real message
5. On long output (>TG_MAX_MESSAGE_CHARS), delegate to long_message_split callback

Rate limiting:
- Throttle mid-stream updates to max 1 per UPDATE_INTERVAL_SEC OR every UPDATE_DELTA_CHARS new chars.
- First chunk always fires immediately so short replies don't appear stalled.
- Final delivery always sent (is_final=True).

Caller contract:
- update_message(text, is_final=False) -> bool
  - is_final=False: mid-stream draft animation (e.g. send_message_draft with same draft_id)
  - is_final=True:  commit terminal message (send a real message; draft auto-dismisses)
- stream_to_telegram returns (accumulated_text, ok). ok=False means the stream was
  interrupted or empty — caller should NOT persist this to qa_log/session history.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Awaitable, Callable

logger = logging.getLogger(__name__)

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
            continue

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
    update_message: Callable[..., Awaitable[bool]],
    text_stream: AsyncGenerator[str, None],
    long_message_split: Callable[[str], Awaitable] | None = None,
) -> tuple[str, bool]:
    """Consume text stream and push updates to Telegram with rate limiting.

    Args:
        initial_send: Async callable that creates the initial placeholder/draft.
            Signature: `async def(text: str) -> Any`. Called once at the start with "生成中...".
        update_message: Async callable that updates or finalizes the message.
            Signature: `async def(text: str, is_final: bool = False) -> bool`.
            is_final=False → mid-stream draft frame; is_final=True → commit final message.
            Returns True if the call succeeded, False otherwise.
        text_stream: Async generator yielding text deltas.
        long_message_split: Optional callable for outputs > TG_MAX_MESSAGE_CHARS.
            Signature: `async def(full_text: str) -> None`. If None, the first
            TG_MAX_MESSAGE_CHARS are delivered via update_message(is_final=True).

    Returns:
        (accumulated_text, ok). ok=False if the stream was interrupted or empty —
        caller should not persist this output to durable history.
    """
    await initial_send("生成中...")

    accumulated = ""
    last_sent_len = 0
    last_update_time = time.time()
    first_chunk_seen = False
    interrupted = False

    try:
        async for chunk in text_stream:
            accumulated += chunk
            now = time.time()

            if not first_chunk_seen:
                # Force first update so short replies render immediately.
                first_chunk_seen = True
                display = accumulated if len(accumulated) <= TG_MAX_MESSAGE_CHARS else accumulated[:TG_MAX_MESSAGE_CHARS] + "\n…"
                ok = await update_message(display, is_final=False)
                if ok:
                    last_update_time = now
                    last_sent_len = len(accumulated)
                continue

            time_elapsed = now - last_update_time
            chars_since_last = len(accumulated) - last_sent_len

            should_update = (
                time_elapsed >= UPDATE_INTERVAL_SEC
                or chars_since_last >= UPDATE_DELTA_CHARS
            )

            if should_update:
                display = accumulated if len(accumulated) <= TG_MAX_MESSAGE_CHARS else accumulated[:TG_MAX_MESSAGE_CHARS] + "\n…"
                ok = await update_message(display, is_final=False)
                if ok:
                    last_update_time = now
                    last_sent_len = len(accumulated)
    except Exception as e:
        logger.warning(f"Stream interrupted: {e}")
        accumulated += f"\n\n⚠️ 生成中斷：{str(e)[:200]}"
        interrupted = True

    empty = not accumulated.strip()
    if empty:
        accumulated = "（無回應）"

    # Final delivery — always with is_final=True so caller can commit the draft.
    if len(accumulated) <= TG_MAX_MESSAGE_CHARS:
        await update_message(accumulated, is_final=True)
    else:
        if long_message_split is not None:
            await long_message_split(accumulated)
        else:
            await update_message(accumulated[:TG_MAX_MESSAGE_CHARS], is_final=True)

    ok = not interrupted and not empty
    return accumulated, ok
