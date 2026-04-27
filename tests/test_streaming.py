"""Tests for streaming.py — stream-json parsing + TG update rate limiting + draft contract."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from streaming import stream_to_telegram, TG_MAX_MESSAGE_CHARS, UPDATE_INTERVAL_SEC


# ─────────────── Helpers ───────────────

class _UpdateRecorder:
    """Records every call to update_message; tracks is_final flag separately."""

    def __init__(self, return_ok: bool = True):
        self.calls: list[str] = []
        self.is_final_calls: list[bool] = []
        self.return_ok = return_ok

    async def __call__(self, text: str, is_final: bool = False) -> bool:
        self.calls.append(text)
        self.is_final_calls.append(is_final)
        return self.return_ok

    @property
    def mid_stream_calls(self) -> list[str]:
        return [t for t, f in zip(self.calls, self.is_final_calls) if not f]

    @property
    def final_calls(self) -> list[str]:
        return [t for t, f in zip(self.calls, self.is_final_calls) if f]


# ─────────────── Tests ───────────────

@pytest.mark.asyncio
async def test_normal_streaming_accumulates_and_finalizes():
    """3 chunks arrive → final text matches concatenation; ok=True; final delivery happens with is_final=True."""
    chunks = ["你好 ", "世界", "！"]
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()

    async def slow_gen():
        for c in chunks:
            yield c
            await asyncio.sleep(UPDATE_INTERVAL_SEC + 0.05)

    final_text, ok = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=slow_gen(),
    )

    assert final_text == "你好 世界！"
    assert ok is True
    initial_send.assert_called_once()
    # The final call must carry is_final=True with full text
    assert update_recorder.final_calls, "expected at least one is_final=True call"
    assert "你好 世界！" in update_recorder.final_calls[-1]


@pytest.mark.asyncio
async def test_first_chunk_triggers_immediate_update():
    """First chunk MUST trigger an update immediately (no throttle), so short replies render fast."""
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()

    async def fast_first_chunk():
        # Single tiny chunk arrives instantly — under both UPDATE_DELTA_CHARS and UPDATE_INTERVAL_SEC.
        # Without first-chunk forcing, it would NOT update mid-stream and short replies appear "stalled".
        yield "Hi"

    final_text, ok = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=fast_first_chunk(),
    )

    assert final_text == "Hi"
    assert ok is True
    # Must have at least one mid-stream call (the first chunk one) — proves draft animation kicks in immediately
    assert len(update_recorder.mid_stream_calls) >= 1, \
        f"expected ≥1 mid-stream update on first chunk; got mid={update_recorder.mid_stream_calls}, all={update_recorder.calls}"
    assert update_recorder.mid_stream_calls[0] == "Hi"


@pytest.mark.asyncio
async def test_stream_interrupted_returns_ok_false_and_marker():
    """Mid-stream exception → ok=False, accumulated contains partial + warning marker."""
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()

    async def bad_gen():
        yield "已產生的部分 "
        raise RuntimeError("subprocess crashed")

    final_text, ok = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=bad_gen(),
    )

    assert ok is False, "interrupted stream must return ok=False so caller skips qa_log write"
    assert "已產生的部分" in final_text
    assert "⚠️" in final_text or "中斷" in final_text


@pytest.mark.asyncio
async def test_empty_stream_shows_no_response_message():
    """Stream yields nothing → final message is 「（無回應）」, ok=False (nothing useful generated)."""
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()

    async def empty_gen():
        if False:
            yield  # pragma: no cover  — empty async generator

    final_text, ok = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=empty_gen(),
    )

    assert final_text == "（無回應）"
    assert ok is False
    # The "（無回應）" should appear in the final-flag call
    assert any("無回應" in c for c in update_recorder.final_calls)


@pytest.mark.asyncio
async def test_long_output_triggers_split_callback():
    """Output > TG_MAX_MESSAGE_CHARS → long_message_split callable invoked with full text."""
    big_chunk = "字" * (TG_MAX_MESSAGE_CHARS + 500)
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()
    long_split_recorder = AsyncMock()

    async def big_gen():
        yield big_chunk

    final_text, ok = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=big_gen(),
        long_message_split=long_split_recorder,
    )

    assert ok is True
    assert len(final_text) > TG_MAX_MESSAGE_CHARS
    long_split_recorder.assert_called_once()
    args, kwargs = long_split_recorder.call_args
    full_text_arg = args[0] if args else kwargs.get("full_text", "")
    assert len(full_text_arg) > TG_MAX_MESSAGE_CHARS


@pytest.mark.asyncio
async def test_rate_limiting_throttles_rapid_small_chunks():
    """10 small chunks emitted instantly → mid-stream calls bounded (first-chunk force + throttle), final once."""
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()

    async def rapid_small_gen():
        for _ in range(10):
            yield "12345"

    final_text, ok = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=rapid_small_gen(),
    )

    assert ok is True
    assert final_text == "12345" * 10
    # First chunk forces 1 update; remaining 9 chunks (45 chars) total stay under 50-char delta within ms → 0 extra mid.
    # Final delivery → 1 is_final=True call.
    # Total expected: 1 mid + 1 final = 2. Allow some slack: ≤ 3 mid, exactly 1 final.
    assert len(update_recorder.mid_stream_calls) <= 3, \
        f"expected ≤ 3 mid-stream calls; got {len(update_recorder.mid_stream_calls)}"
    assert len(update_recorder.final_calls) == 1, \
        f"expected exactly 1 final call; got {len(update_recorder.final_calls)}"


@pytest.mark.asyncio
async def test_final_delivery_uses_is_final_flag():
    """Verify is_final flag is used to distinguish mid-stream draft updates from terminal commit."""
    initial_send = AsyncMock()
    update_recorder = _UpdateRecorder()

    async def two_chunks():
        yield "A"
        await asyncio.sleep(UPDATE_INTERVAL_SEC + 0.05)
        yield "B"

    final_text, ok = await stream_to_telegram(
        initial_send=initial_send,
        update_message=update_recorder,
        text_stream=two_chunks(),
    )

    assert ok is True
    assert final_text == "AB"
    # Mid-stream calls must NOT have is_final=True
    assert all(f is False for f in update_recorder.is_final_calls[:-1])
    # Last call must have is_final=True
    assert update_recorder.is_final_calls[-1] is True


# ─────────────── Bonus: stream-json parsing ───────────────

@pytest.mark.asyncio
async def test_claude_stream_parses_text_deltas_only():
    """claude_stream extracts only content_block_delta text_delta events; skips noise."""
    from streaming import claude_stream

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
