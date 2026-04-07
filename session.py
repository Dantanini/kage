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
    repo_name: str | None = None
    repo_path: str | None = None
    last_active: float = field(default_factory=time.time)
    is_first_message: bool = True
    qa_log: list = field(default_factory=list)  # [(prompt, response), ...]
    _on_start_hooks: list[SessionHook] = field(default_factory=list)
    _on_end_hooks: list[SessionHook] = field(default_factory=list)
    _save_timer: object | None = field(default=None, repr=False)
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
        self._schedule_auto_save()

    def _schedule_auto_save(self, delay_minutes: int = 29) -> None:
        """Reset the auto-save timer. Fires end hooks after delay_minutes of inactivity."""
        # Cancel previous timer
        if self._save_timer and not self._save_timer.done():
            self._save_timer.cancel()

        async def _auto_save():
            try:
                await asyncio.sleep(delay_minutes * 60)
                logger.info(f"Auto-save triggered for session {self.session_id[:8]}")
                await self.run_end_hooks()
            except asyncio.CancelledError:
                pass  # Timer was reset by new message, this is normal
            except Exception as e:
                logger.warning(f"Auto-save failed: {e}")

        try:
            loop = asyncio.get_running_loop()
            self._save_timer = loop.create_task(_auto_save())
        except RuntimeError:
            pass  # No event loop (e.g. in tests)

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
            # Auto-save timer already handles memory save,
            # no need to trigger end hooks again here
            return None
        return session

    def create(self, user_id: int, intent: str, model: str,
               repo_name: str | None = None, repo_path: str | None = None) -> Session:
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            intent=intent,
            model=model,
            repo_name=repo_name,
            repo_path=repo_path,
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
            # Cancel auto-save timer to prevent duplicate saves
            if session._save_timer and not session._save_timer.done():
                session._save_timer.cancel()
            await session.run_end_hooks()
        return session

    def close_sync(self, user_id: int) -> Session | None:
        """Close session without running hooks (for non-async contexts)."""
        session = self._sessions.pop(user_id, None)
        if session and session._save_timer and not session._save_timer.done():
            session._save_timer.cancel()
        return session

    def get_or_create(self, user_id: int, intent: str, model: str,
                      repo_name: str | None = None, repo_path: str | None = None) -> Session:
        existing = self.get(user_id)
        if existing:
            existing.last_active = time.time()
            return existing
        return self.create(user_id, intent, model, repo_name=repo_name, repo_path=repo_path)
