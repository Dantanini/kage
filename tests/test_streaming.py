"""Tests for streaming.py — stream-json parsing + TG update rate limiting."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from streaming import stream_to_telegram, TG_MAX_MESSAGE_CHARS, UPDATE_INTERVAL_SEC


# ─────────────── Helpers ───────────────

async def _async_gen(items, raise_at=None):
    """Yield items one by one. If raise_at is set, raise RuntimeError at that index."""
    for i, item in enumerate(items):
        if raise_at is not None and i == raise_at:
            raise RuntimeError("simulated mid-stream failure")
        yield item


class _UpdateRecorder:
    """Records every call to update_message; controls return value."""

    def __init__(self, return_ok: bool = True):
        self.calls: list[str] = []
        self.return_ok = return_ok

    async def __call__(self, text: str) -> bool:
        self.calls.append(text)
        return self.return_ok


# ─────────────── Tests ───────────────

@pytest.mark.asyncio
async def test_normal_streaming_accumulates_and_finalizes():
    """3 chunks arrive → final text matches concatenation; final delivery happens."""
    chunks = ["你好 ", "世界", "！"]
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()

    # Force every chunk to update by waiting between yields
    async def slow_gen():
        for c in chunks:
            yield c
            await asyncio.sleep(UPDATE_INTERVAL_SEC + 0.05)

    final_text = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=slow_gen(),
    )

    assert final_text == "你好 世界！"
    initial_send.assert_called_once()
    # Should have at least 1 final call with full text
    assert any("你好 世界！" in call for call in update_recorder.calls)


@pytest.mark.asyncio
async def test_stream_interrupted_appends_warning_marker():
    """Mid-stream exception → final text contains partial content + warning marker."""
    chunks = ["partial 內容 ", "更多內容 "]
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()

    async def bad_gen():
        yield "已產生的部分 "
        raise RuntimeError("subprocess crashed")

    final_text = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=bad_gen(),
    )

    assert "已產生的部分" in final_text
    assert "⚠️" in final_text or "中斷" in final_text


@pytest.mark.asyncio
async def test_empty_stream_shows_no_response_message():
    """Stream yields nothing → final message is 「（無回應）」."""
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()

    async def empty_gen():
        if False:
            yield  # pragma: no cover  — empty async generator

    final_text = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=empty_gen(),
    )

    assert final_text == "（無回應）"
    # The "（無回應）" should be in the final update call
    assert any("無回應" in call for call in update_recorder.calls)


@pytest.mark.asyncio
async def test_long_output_triggers_split_callback():
    """Output > TG_MAX_MESSAGE_CHARS → long_message_split callable invoked with full text."""
    big_chunk = "字" * (TG_MAX_MESSAGE_CHARS + 500)
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()
    long_split_recorder = AsyncMock()

    async def big_gen():
        yield big_chunk

    final_text = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=big_gen(),
        long_message_split=long_split_recorder,
    )

    assert len(final_text) > TG_MAX_MESSAGE_CHARS
    long_split_recorder.assert_called_once()
    # Verify the full text was passed to split callable
    args, kwargs = long_split_recorder.call_args
    full_text_arg = args[0] if args else kwargs.get("full_text", "")
    assert len(full_text_arg) > TG_MAX_MESSAGE_CHARS


@pytest.mark.asyncio
async def test_rate_limiting_throttles_rapid_small_chunks():
    """10 small chunks (< UPDATE_DELTA_CHARS each) within milliseconds → bot.update_message called ≤ 2 times during stream + 1 final."""
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()

    async def rapid_small_gen():
        # 10 chunks of 5 chars each = 50 chars total — should NOT trigger UPDATE_DELTA_CHARS
        # Time elapsed should be << UPDATE_INTERVAL_SEC
        for _ in range(10):
            yield "12345"
            # No sleep — emit as fast as possible

    final_text = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=rapid_small_gen(),
    )

    # All 50 chars should be in final
    assert final_text == "12345" * 10
    # During stream itself, at most 1-2 mid-stream updates expected (50 chars total
    # might trigger 1 update at boundary). Plus 1 final update.
    # So total update_message calls should be ≤ 3.
    assert len(update_recorder.calls) <= 3, f"Expected ≤ 3 updates, got {len(update_recorder.calls)}"


# ─────────────── Bonus: stream-json parsing ───────────────

@pytest.mark.asyncio
async def test_claude_stream_parses_text_deltas_only():
    """claude_stream extracts only content_block_delta text_delta events; skips noise."""
    from streaming import claude_stream

    # Construct fake stdout lines
    fake_stdout_lines = [
        json.dumps({"type": "system", "subtype": "init"}) + "\n",
        json.dumps({
            "type": "stream_event",
            "event": {"type": "message_start", "message": {}},
        }) + "\n",
        json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello "}},
        }) + "\n",
        json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "World"}},
        }) + "\n",
        json.dumps({
            "type": "stream_event",
            "event": {"type": "message_stop"},
        }) + "\n",
        b"non-JSON debug noise that should be skipped\n".decode(),
        json.dumps({"type": "result", "subtype": "success"}) + "\n",
    ]

    # Build fake subprocess
    fake_stdout = MagicMock()
    fake_stdout.readline = AsyncMock(side_effect=[line.encode() for line in fake_stdout_lines] + [b""])

    fake_stdin = MagicMock()
    fake_stdin.write = MagicMock()
    fake_stdin.drain = AsyncMock()
    fake_stdin.close = MagicMock()

    fake_stderr = MagicMock()
    fake_stderr.read = AsyncMock(return_value=b"")

    fake_proc = MagicMock()
    fake_proc.stdin = fake_stdin
    fake_proc.stdout = fake_stdout
    fake_proc.stderr = fake_stderr
    fake_proc.wait = AsyncMock(return_value=0)
    fake_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)):
        deltas = []
        async for chunk in claude_stream(["claude", "-p"], "test prompt"):
            deltas.append(chunk)

    assert deltas == ["Hello ", "World"]
