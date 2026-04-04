"""PlanStore v2 — pure file-based plan management, no LLM needed.

Plans are stored in .local/plan/ (git-ignored) to avoid leaking
private content to public repos. Completed plans are archived
and can be summarized into dev-journal by /evening workflow.
"""

import logging
from datetime import date, datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PlanStatus(Enum):
    EMPTY = "empty"
    DRAFT = "draft"
    PLANNED = "planned"
    EXECUTING = "executing"


# Workflow instructions prepended to every plan injection.
PLAN_INSTRUCTIONS = """\
## Instructions
- 每個 task 開獨立 feature branch from develop
- commit 前必須 `git branch --show-current` 確認不在 main/develop
- 完成一個 task 後等待 bot 發下一個，不要自行跳到下一項
- **不要直接開 PR**，等用戶在 TG 按「開 PR」按鈕
- PR 一律透過 `scripts/pr.sh` 開，寫死 `--base develop`
"""


class PlanStore:
    """Manages plan lifecycle: draft → planned → executing → archived."""

    def __init__(self, local_dir: str):
        self._local_dir = local_dir
        self._plan_dir = Path(local_dir) / "plan"
        self._plan_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir = self._plan_dir / "archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _current_file(self) -> Path:
        return self._plan_dir / "current.md"

    @property
    def _status_file(self) -> Path:
        return self._plan_dir / "status"

    @property
    def status(self) -> PlanStatus:
        if not self._status_file.exists():
            return PlanStatus.EMPTY
        raw = self._status_file.read_text(encoding="utf-8").strip()
        try:
            return PlanStatus(raw)
        except ValueError:
            return PlanStatus.EMPTY

    def _set_status(self, status: PlanStatus) -> None:
        self._status_file.write_text(status.value, encoding="utf-8")

    def has_plan(self) -> bool:
        return self._current_file.exists() and self._current_file.read_text(encoding="utf-8").strip() != ""

    def read(self) -> str:
        if not self._current_file.exists():
            return ""
        return self._current_file.read_text(encoding="utf-8").strip()

    def append(self, content: str) -> None:
        """Append user input to draft. No LLM involved."""
        existing = self.read()
        today = date.today().isoformat()
        if existing:
            new = existing + f"\n- {content.strip()}\n"
        else:
            new = f"# Plan ({today})\n\n## 待整理\n- {content.strip()}\n"
        self._current_file.write_text(new, encoding="utf-8")
        if self.status == PlanStatus.EMPTY:
            self._set_status(PlanStatus.DRAFT)

    def set_planned(self, plan_content: str) -> None:
        """Opus has analyzed and produced an ordered checklist."""
        if self.status == PlanStatus.EMPTY:
            raise ValueError("沒有草稿可以規劃")
        existing = self.read()
        today = date.today().isoformat()
        full = f"# Plan ({today})\n\n{plan_content.strip()}\n"
        self._current_file.write_text(full, encoding="utf-8")
        self._set_status(PlanStatus.PLANNED)

    def set_executing(self) -> None:
        """Start execution."""
        if self.status not in (PlanStatus.PLANNED,):
            raise ValueError("沒有計畫可以執行")
        self._set_status(PlanStatus.EXECUTING)

    def pause(self) -> None:
        """Pause execution, go back to planned state."""
        self._set_status(PlanStatus.PLANNED)

    def complete_item(self, item_substring: str) -> None:
        """Mark a checklist item as done by matching substring."""
        content = self.read()
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "- [ ]" in line and item_substring in line:
                lines[i] = line.replace("- [ ]", "- [x]", 1)
                break
        self._current_file.write_text("\n".join(lines), encoding="utf-8")

    def all_completed(self) -> bool:
        """Check if all checklist items are done."""
        content = self.read()
        return "- [x]" in content and "- [ ]" not in content

    def pending_items(self) -> list[str]:
        """Get list of uncompleted items."""
        content = self.read()
        return [
            line.strip()
            for line in content.split("\n")
            if "- [ ]" in line
        ]

    def archive_completed(self) -> str:
        """Move completed items to archive, keep pending in current.
        Returns archived content. If all done, reset to EMPTY.
        """
        content = self.read()
        lines = content.split("\n")

        completed = []
        remaining = []
        for line in lines:
            if "- [x]" in line:
                completed.append(line)
            else:
                remaining.append(line)

        # Write archive
        archived_text = "\n".join(completed)
        if archived_text.strip():
            today = date.today().isoformat()
            ts = datetime.now().strftime("%H%M%S")
            archive_file = self._archive_dir / f"{today}-{ts}.md"
            archive_file.write_text(
                f"# Archived Plan ({today})\n\n{archived_text}\n",
                encoding="utf-8",
            )

        # Update current
        remaining_text = "\n".join(remaining).strip()
        has_pending = any("- [ ]" in line for line in remaining)

        if has_pending:
            self._current_file.write_text(remaining_text + "\n", encoding="utf-8")
        else:
            # All done, clean up
            self._current_file.unlink(missing_ok=True)
            self._status_file.unlink(missing_ok=True)

        return archived_text

    def build_context_injection(self) -> str:
        """Build a context block for prompt injection."""
        content = self.read()
        if not content:
            return ""

        if self.status in (PlanStatus.PLANNED, PlanStatus.EXECUTING):
            return (
                f"[Session 計畫]\n"
                f"{PLAN_INSTRUCTIONS}\n"
                f"{content}\n"
                f"[/Session 計畫]\n\n"
            )
        else:
            # Draft — just show what's been collected
            return (
                f"[計畫草稿 — 尚未規劃]\n"
                f"{content}\n"
                f"[/計畫草稿]\n\n"
            )
