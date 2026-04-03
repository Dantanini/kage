"""Plan store — write plans during fragmented time, consume at next core session.

File-based, no LLM needed. Plans are stored in dev-journal/memory/ alongside
other memory files so both kage and Claude Code can access them.
"""

import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

PLAN_FILENAME = "next-session-plan.md"

# Workflow instructions prepended to every plan injection.
# User never sees this in the plan file — it's added at injection time.
PLAN_INSTRUCTIONS = """\
## Instructions
- 每個 task 開獨立 feature branch from develop
- commit 前必須 `git branch --show-current` 確認不在 main/develop
- 完成一個 task 後立即呼叫 `python3 scripts/task_done.py` 發通知
- **不要直接開 PR**，等用戶在 TG 按「開 PR」按鈕
- PR 一律透過 `scripts/pr.sh` 開，寫死 `--base develop`
"""


class PlanStore:
    """Manages the next-session plan file."""

    def __init__(self, base_dir: str):
        self._dir = Path(base_dir) / "memory"
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._dir / PLAN_FILENAME

    def has_plan(self) -> bool:
        return self.path.exists() and self.path.read_text(encoding="utf-8").strip() != ""

    def read(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8").strip()

    def write(self, content: str) -> None:
        """Write (overwrite) the plan file."""
        today = date.today().isoformat()
        text = f"# Next Session Plan ({today})\n\n{content.strip()}\n"
        self.path.write_text(text, encoding="utf-8")

    def append(self, content: str) -> None:
        """Append to existing plan."""
        existing = self.read()
        if existing:
            full = existing + f"\n{content.strip()}\n"
            self.path.write_text(full + "\n", encoding="utf-8")
        else:
            self.write(content)

    def consume(self) -> str:
        """Read the plan and delete the file. Returns empty string if no plan."""
        content = self.read()
        if content:
            self.path.unlink(missing_ok=True)
        return content

    def build_context_injection(self) -> str:
        """Build a context block for prompt injection. Empty if no plan.

        Prepends workflow instructions so every model reading the plan
        knows the rules (call task_done.py, don't open PR directly, etc.).
        """
        content = self.read()
        if not content:
            return ""
        return (
            f"[下次 Session 計畫 — 碎片時間預先準備的任務清單]\n"
            f"{PLAN_INSTRUCTIONS}\n"
            f"## Tasks\n{content}\n"
            f"[/下次 Session 計畫]\n\n"
        )
