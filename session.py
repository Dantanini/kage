"""Session 管理 — 追蹤活躍對話，支援 --resume 和 lifecycle hooks。"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# Hook type: async callable that receives the session
SessionHook = Callable[["Session"], Awaitable[None]]


@dataclass
class Session:
    session_id: str
    user_id: int
    intent: str
    model: str
    last_active: float = field(default_factory=time.time)
    is_first_message: bool = True
    qa_log: list = field(default_factory=list)  # [(prompt, response), ...]
    _on_start_hooks: list[SessionHook] = field(default_factory=list)
    _on_end_hooks: list[SessionHook] = field(default_factory=list)
    _started: bool = False

    def add_start_hook(self, hook: SessionHook) -> None:
        self._on_start_hooks.append(hook)

    def add_end_hook(self, hook: SessionHook) -> None:
        self._on_end_hooks.append(hook)

    async def run_start_hooks(self) -> list[str]:
        """Run all start hooks. Returns list of error messages (empty = all OK)."""
        if self._started:
            return []
        self._started = True
        errors = []
        for hook in self._on_start_hooks:
            try:
                await hook(self)
            except Exception as e:
                msg = f"start hook failed: {e}"
                logger.warning(msg)
                errors.append(msg)
        return errors

    async def run_end_hooks(self) -> list[str]:
        """Run all end hooks. Returns list of error messages (empty = all OK)."""
        errors = []
        for hook in self._on_end_hooks:
            try:
                await hook(self)
            except Exception as e:
                msg = f"end hook failed: {e}"
                logger.warning(msg)
                errors.append(msg)
        return errors

    def touch(self):
        self.last_active = time.time()
        self.is_first_message = False

    def qa_log_size(self) -> int:
        return sum(len(q) + len(a) for q, a in self.qa_log)

    def is_expired(self, timeout_seconds: int = 1800) -> bool:
        return (time.time() - self.last_active) > timeout_seconds


class SessionManager:
    def __init__(self, timeout_minutes: int = 30):
        self._sessions: dict[int, Session] = {}
        self._timeout = timeout_minutes * 60
        self._start_hook_factories: list[Callable[[], SessionHook]] = []
        self._end_hook_factories: list[Callable[[], SessionHook]] = []

    def register_start_hook(self, factory: Callable[[], SessionHook]) -> None:
        """Register a factory that creates a start hook for each new session."""
        self._start_hook_factories.append(factory)

    def register_end_hook(self, factory: Callable[[], SessionHook]) -> None:
        """Register a factory that creates an end hook for each new session."""
        self._end_hook_factories.append(factory)

    def get(self, user_id: int) -> Session | None:
        session = self._sessions.get(user_id)
        if session and session.is_expired(self._timeout):
            del self._sessions[user_id]
            return None
        return session

    def create(self, user_id: int, intent: str, model: str) -> Session:
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            intent=intent,
            model=model,
        )
        # Attach registered hooks
        for factory in self._start_hook_factories:
            session.add_start_hook(factory())
        for factory in self._end_hook_factories:
            session.add_end_hook(factory())
        self._sessions[user_id] = session
        return session

    async def close(self, user_id: int) -> Session | None:
        """Close session and run end hooks. Now async."""
        session = self._sessions.pop(user_id, None)
        if session:
            await session.run_end_hooks()
        return session

    def close_sync(self, user_id: int) -> Session | None:
        """Close session without running hooks (for non-async contexts)."""
        return self._sessions.pop(user_id, None)

    def get_or_create(self, user_id: int, intent: str, model: str) -> Session:
        existing = self.get(user_id)
        if existing:
            existing.last_active = time.time()
            return existing
        return self.create(user_id, intent, model)
