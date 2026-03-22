"""訊息合併器 — 等使用者打完再送出。

規則：
- 收到訊息後開始倒數（預設 5 秒）
- 倒數期間收到新訊息 → 重新計時
- 倒數結束 → 合併所有訊息送出
- 最大等待時間 30 秒（避免無限等）
"""

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class PendingBatch:
    messages: list[str] = field(default_factory=list)
    first_received: float = field(default_factory=time.time)
    last_received: float = field(default_factory=time.time)
    task: asyncio.Task | None = None


class MessageBatcher:
    def __init__(
        self,
        delay_seconds: float = 5.0,
        max_wait_seconds: float = 30.0,
    ):
        self._delay = delay_seconds
        self._max_wait = max_wait_seconds
        self._batches: dict[int, PendingBatch] = {}
        self._callbacks: dict[int, asyncio.Event] = {}

    async def add(self, user_id: int, text: str) -> str | None:
        """Add a message. Returns merged text when batch is ready, None if still waiting."""
        batch = self._batches.get(user_id)

        if batch is None:
            # First message — start new batch
            batch = PendingBatch()
            self._batches[user_id] = batch
            self._callbacks[user_id] = asyncio.Event()

        batch.messages.append(text)
        batch.last_received = time.time()

        # Cancel existing timer
        if batch.task and not batch.task.done():
            batch.task.cancel()

        # Check max wait
        elapsed = time.time() - batch.first_received
        remaining = max(0.5, self._max_wait - elapsed)
        wait_time = min(self._delay, remaining)

        if elapsed >= self._max_wait:
            # Max wait reached, flush immediately
            return self._flush(user_id)

        # Start new timer
        event = self._callbacks[user_id]
        event.clear()
        batch.task = asyncio.create_task(self._wait_and_signal(user_id, wait_time))

        # Wait for the signal
        try:
            await asyncio.wait_for(event.wait(), timeout=wait_time + 1)
        except asyncio.TimeoutError:
            pass

        # Only the last waiter should flush
        if user_id in self._batches and time.time() - batch.last_received >= self._delay * 0.9:
            return self._flush(user_id)

        return None

    async def _wait_and_signal(self, user_id: int, delay: float):
        try:
            await asyncio.sleep(delay)
            if user_id in self._callbacks:
                self._callbacks[user_id].set()
        except asyncio.CancelledError:
            pass

    def _flush(self, user_id: int) -> str:
        batch = self._batches.pop(user_id, None)
        self._callbacks.pop(user_id, None)
        if batch:
            return "\n".join(batch.messages)
        return ""
