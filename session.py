"""Session 管理 — 追蹤活躍對話，支援 --resume。"""

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    session_id: str
    user_id: int
    intent: str
    model: str
    last_active: float = field(default_factory=time.time)
    is_first_message: bool = True

    def touch(self):
        self.last_active = time.time()
        self.is_first_message = False

    def is_expired(self, timeout_seconds: int = 1800) -> bool:
        return (time.time() - self.last_active) > timeout_seconds


class SessionManager:
    def __init__(self, timeout_minutes: int = 30):
        self._sessions: dict[int, Session] = {}
        self._timeout = timeout_minutes * 60

    def get(self, user_id: int) -> Session | None:
        session = self._sessions.get(user_id)
        if session and session.is_expired(self._timeout):
            del self._sessions[user_id]
            return None
        return session

    def create(self, user_id: int, intent: str, model: str) -> Session:
        session = Session(
            session_id=str(uuid.uuid4())[:8],
            user_id=user_id,
            intent=intent,
            model=model,
        )
        self._sessions[user_id] = session
        return session

    def close(self, user_id: int) -> Session | None:
        return self._sessions.pop(user_id, None)

    def get_or_create(self, user_id: int, intent: str, model: str) -> Session:
        existing = self.get(user_id)
        if existing:
            existing.touch()
            return existing
        return self.create(user_id, intent, model)
