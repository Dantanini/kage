"""Persistent memory layer — inspired by Claude Code's memdir system.

Reads/writes structured memory files that persist across sessions.
Supports both legacy single-file and new structured directory format.
Includes event-driven MemoryWriter for immediate writes on important events.
"""

import logging
import re
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_FILENAME = "kage-memory.md"
DEFAULT_MEMORY_DIRNAME = "kage-memory"
MEMORY_INJECT_LIMIT = 10000  # chars to inject into prompt

# Read order matters: read() truncates by keeping the TAIL, so the file most
# critical for "current state" must come LAST to survive truncation.
# active-tasks.md = current PRs + open decisions = most critical → goes last.
STRUCTURED_FILES = ["session-log.md", "lessons-learned.md", "active-tasks.md"]


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from markdown content."""
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return text


class MemoryStore:
    """File-backed memory store supporting structured directory or single file."""

    def __init__(self, base_dir: str, filename: str = DEFAULT_MEMORY_FILENAME):
        self._repo_root = Path(base_dir)
        self._base = self._repo_root / "memory"
        self._base.mkdir(parents=True, exist_ok=True)
        self._single_path = self._base / filename
        self._dir_path = self._base / DEFAULT_MEMORY_DIRNAME

    @property
    def path(self) -> Path:
        """Legacy property — returns single file path for backward compat."""
        return self._single_path

    @property
    def structured_dir(self) -> Path:
        return self._dir_path

    def _use_structured(self) -> bool:
        """Check if structured directory exists and has files."""
        return self._dir_path.is_dir() and any(self._dir_path.glob("*.md"))

    def exists(self) -> bool:
        return self._use_structured() or self._single_path.exists()

    def read(self, limit: int = MEMORY_INJECT_LIMIT) -> str:
        """Read memory content from structured dir or single file."""
        try:
            if self._use_structured():
                content = self._read_structured()
            elif self._single_path.exists():
                content = self._single_path.read_text(encoding="utf-8").strip()
            else:
                return ""

            if len(content) > limit:
                content = "...(truncated)...\n" + content[-limit:]
            return content
        except Exception as e:
            logger.warning(f"Failed to read memory: {e}")
            return ""

    def _read_structured(self) -> str:
        """Read and merge all structured memory files, stripping frontmatter."""
        parts = []
        for fname in STRUCTURED_FILES:
            fpath = self._dir_path / fname
            if fpath.exists():
                raw = fpath.read_text(encoding="utf-8").strip()
                parts.append(_strip_frontmatter(raw))
        # Also read any extra .md files not in the standard list
        for fpath in sorted(self._dir_path.glob("*.md")):
            if fpath.name not in STRUCTURED_FILES:
                raw = fpath.read_text(encoding="utf-8").strip()
                parts.append(_strip_frontmatter(raw))
        return "\n\n".join(parts)

    def check_recovery_needed(self, marker_path: Path) -> str:
        """Check if the previous session ended abnormally.

        If marker file exists, read its mtime, delete it, and return a warning.
        If not, return empty string.
        """
        if not marker_path.exists():
            return ""
        try:
            mtime = datetime.fromtimestamp(marker_path.stat().st_mtime)
            marker_path.unlink()
            return (
                f"[系統提示] 上次對話異常中斷（可能因重啟或當機），"
                f"時間約 {mtime.strftime('%Y-%m-%d %H:%M')}，"
                f"最後的對話內容可能未儲存到記憶。請主動告知使用者此狀況。\n\n"
            )
        except Exception as e:
            logger.warning(f"Failed to check recovery marker: {e}")
            return ""

    def read_global_context(self, max_log_lines: int = 10, index_limit: int = 1500) -> str:
        """Read global knowledge base context from INDEX.md and log.md.

        These files live at the repo root (not in memory/).
        Returns empty string if neither file exists.
        """
        parts = []

        # Read INDEX.md (truncated)
        index_path = self._repo_root / "INDEX.md"
        if index_path.exists():
            try:
                content = index_path.read_text(encoding="utf-8").strip()
                if len(content) > index_limit:
                    content = content[:index_limit] + "\n...(truncated)"
                parts.append(content)
            except Exception as e:
                logger.warning(f"Failed to read INDEX.md: {e}")

        # Read log.md (last N lines)
        log_path = self._repo_root / "log.md"
        if log_path.exists():
            try:
                lines = log_path.read_text(encoding="utf-8").strip().splitlines()
                # Keep only lines starting with ## (entries), take last N
                entries = [l for l in lines if l.startswith("## [")]
                recent = entries[-max_log_lines:] if len(entries) > max_log_lines else entries
                if recent:
                    parts.append("[Recent Operations]\n" + "\n".join(recent))
            except Exception as e:
                logger.warning(f"Failed to read log.md: {e}")

        return "\n\n".join(parts) if parts else ""

    def build_context_prefix(self) -> str:
        """Build the memory prefix to inject into prompts. Empty string if no memory."""
        content = self.read()
        global_ctx = self.read_global_context()

        if not content and not global_ctx:
            return ""

        parts = []
        if content:
            parts.append(f"[持久記憶 — 來自過去對話的重要脈絡]\n{content}\n[/持久記憶]")
        if global_ctx:
            parts.append(f"[知識庫概覽]\n{global_ctx}\n[/知識庫概覽]")
        return "\n\n".join(parts) + "\n\n"

    def build_save_prompt(self, qa_pairs: list[tuple[str, str]], max_pairs: int = 5) -> str:
        """Build a prompt that asks Claude to update the memory files.

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

        if self._use_structured():
            session_log = self._dir_path / "session-log.md"
            active_tasks = self._dir_path / "active-tasks.md"
            lessons = self._dir_path / "lessons-learned.md"
            return (
                f"以下是這次對話的近期問答摘要。請更新結構化記憶檔案：\n\n"
                f"1. **Session 摘要** → 讀取並更新 `{session_log}`\n"
                f"   - 用 `## YYYY-MM-DD` 作為段落標題，追加今天的 session 摘要\n"
                f"   - 如果超過 100 行，刪除最舊的段落\n"
                f"2. **待辦更新** → 讀取並更新 `{active_tasks}`\n"
                f"   - 更新 PR 狀態、新增/移除待辦項目\n"
                f"3. **教訓記錄** → 讀取並更新 `{lessons}`\n"
                f"   - 如果這次對話有新的操作教訓或工作流程修正，追加到檔案\n"
                f"4. 不要記流水帳，只記對未來對話有用的資訊\n"
                f"5. 每個檔案都有 YAML frontmatter，更新 `updated` 日期\n\n"
                f"{log_text}"
            )

        return (
            f"以下是這次對話的近期問答摘要。請讀取 {self._single_path} "
            f"（如不存在請建立），然後：\n"
            f"1. 從這次對話中提取值得長期記住的關鍵資訊（決策、偏好、進度、問題）\n"
            f"2. 追加到檔案末尾，用 `## YYYY-MM-DD` 作為段落標題\n"
            f"3. 如果檔案超過 100 行，刪除最舊的段落\n"
            f"4. 不要記流水帳，只記對未來對話有用的資訊\n\n"
            f"{log_text}"
        )


class MemoryWriter:
    """Event-driven writer for immediate memory updates.

    Writes directly to structured memory files without going through Claude.
    Designed to work alongside the debounce-based save mechanism.
    """

    def __init__(self, store: MemoryStore):
        self._store = store

    def _get_file(self, name: str) -> Path | None:
        """Get a structured memory file path. Returns None if dir doesn't exist."""
        d = self._store.structured_dir
        if not d.is_dir():
            return None
        return d / name

    def _update_frontmatter_date(self, path: Path) -> None:
        """Update the 'updated' field in YAML frontmatter to today."""
        content = path.read_text(encoding="utf-8")
        today = date.today().isoformat()
        content = re.sub(
            r"^(updated:\s*)\d{4}-\d{2}-\d{2}",
            rf"\g<1>{today}",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        path.write_text(content, encoding="utf-8")

    def write_lesson(self, lesson: str) -> None:
        """Append a lesson to lessons-learned.md."""
        path = self._get_file("lessons-learned.md")
        if not path or not path.exists():
            return
        content = path.read_text(encoding="utf-8")
        content = content.rstrip() + f"\n- {lesson}\n"
        path.write_text(content, encoding="utf-8")
        self._update_frontmatter_date(path)

    def write_task_update(self, update: str) -> None:
        """Append a task update to active-tasks.md."""
        path = self._get_file("active-tasks.md")
        if not path or not path.exists():
            return
        content = path.read_text(encoding="utf-8")
        content = content.rstrip() + f"\n- {update}\n"
        path.write_text(content, encoding="utf-8")
        self._update_frontmatter_date(path)

    def write_session_summary(self, summary: str) -> None:
        """Append a session summary to session-log.md under today's date header."""
        path = self._get_file("session-log.md")
        if not path or not path.exists():
            return
        content = path.read_text(encoding="utf-8")
        today = date.today().isoformat()
        header = f"## {today}"

        if header in content:
            # Append under existing date section
            content = content.rstrip() + f"\n- {summary}\n"
        else:
            # Add new date section
            content = content.rstrip() + f"\n\n{header}\n\n- {summary}\n"

        path.write_text(content, encoding="utf-8")
        self._update_frontmatter_date(path)
