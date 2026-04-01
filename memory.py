"""Persistent memory layer — inspired by Claude Code's memdir system.

Reads/writes a markdown memory file that persists across sessions.
Injected into prompts at session start, updated at session end.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_FILENAME = "kage-memory.md"
MEMORY_INJECT_LIMIT = 2000  # chars to inject into prompt


class MemoryStore:
    """Simple file-backed memory store using a markdown file."""

    def __init__(self, base_dir: str, filename: str = DEFAULT_MEMORY_FILENAME):
        self._path = Path(base_dir) / "memory" / filename
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()

    def read(self, limit: int = MEMORY_INJECT_LIMIT) -> str:
        """Read memory content, truncated to limit chars."""
        if not self._path.exists():
            return ""
        try:
            content = self._path.read_text(encoding="utf-8").strip()
            if len(content) > limit:
                # Truncate from beginning, keep recent memories
                content = "...(truncated)...\n" + content[-limit:]
            return content
        except Exception as e:
            logger.warning(f"Failed to read memory: {e}")
            return ""

    def build_context_prefix(self) -> str:
        """Build the memory prefix to inject into prompts. Empty string if no memory."""
        content = self.read()
        if not content:
            return ""
        return f"[持久記憶 — 來自過去對話的重要脈絡]\n{content}\n[/持久記憶]\n\n"

    def build_save_prompt(self, qa_pairs: list[tuple[str, str]], max_pairs: int = 5) -> str:
        """Build a prompt that asks Claude to update the memory file.

        Args:
            qa_pairs: Recent (question, answer) pairs from the session.
            max_pairs: Max number of recent pairs to include.
        """
        recent = qa_pairs[-max_pairs:]
        if not recent:
            return ""

        log_text = "\n\n---\n\n".join(
            f"**問：** {q[:300]}\n**答：** {a[:300]}" for q, a in recent
        )

        return (
            f"以下是這次對話的近期問答摘要。請讀取 {self._path} "
            f"（如不存在請建立），然後：\n"
            f"1. 從這次對話中提取值得長期記住的關鍵資訊（決策、偏好、進度、問題）\n"
            f"2. 追加到檔案末尾，用 `## YYYY-MM-DD` 作為段落標題\n"
            f"3. 如果檔案超過 100 行，刪除最舊的段落\n"
            f"4. 不要記流水帳，只記對未來對話有用的資訊\n\n"
            f"{log_text}"
        )
