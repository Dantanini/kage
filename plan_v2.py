"""PlanStore v2 — pure file-based plan management, no LLM needed.

Plans are stored in .local/plan/ (git-ignored) to avoid leaking
private content to public repos. Completed plans are archived
and can be summarized into dev-journal by /evening workflow.

File structure (current.md):
  ## 待整理     — user's raw input, pure append
  ## 已規劃     — Opus-produced ordered checklist
  ## 已完成     — completed items moved here
"""

import logging
import re
from datetime import date, datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PlanStatus(Enum):
    EMPTY = "empty"
    DRAFT = "draft"        # has 待整理 only
    PLANNED = "planned"    # has 已規劃 (may also have 待整理)
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
    """Manages plan lifecycle with three sections: 待整理 / 已規劃 / 已完成."""

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

    def _update_status_from_content(self) -> None:
        """Recalculate status based on file content."""
        content = self.read()
        if not content:
            self._status_file.unlink(missing_ok=True)
            return
        has_planned = "## 已規劃" in content and "- [ ]" in content
        has_draft = "## 待整理" in content and any(
            line.strip().startswith("- ") for line in self._get_section("待整理").split("\n") if line.strip()
        )
        if has_planned:
            if self.status != PlanStatus.EXECUTING:
                self._set_status(PlanStatus.PLANNED)
        elif has_draft:
            self._set_status(PlanStatus.DRAFT)
        else:
            self._status_file.unlink(missing_ok=True)

    def has_plan(self) -> bool:
        return self._current_file.exists() and self._current_file.read_text(encoding="utf-8").strip() != ""

    def read(self) -> str:
        if not self._current_file.exists():
            return ""
        return self._current_file.read_text(encoding="utf-8").strip()

    def _get_section(self, section_name: str) -> str:
        """Extract content under a ## heading."""
        content = self.read()
        pattern = rf"## {re.escape(section_name)}\n(.*?)(?=\n## |\Z)"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _set_section(self, section_name: str, section_content: str) -> None:
        """Set content under a ## heading, creating it if needed."""
        content = self.read()
        today = date.today().isoformat()

        if not content:
            content = f"# Plan ({today})\n"

        pattern = rf"(## {re.escape(section_name)}\n)(.*?)(?=\n## |\Z)"
        replacement = f"## {section_name}\n{section_content.strip()}\n"

        if re.search(pattern, content, re.DOTALL):
            new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        else:
            new_content = content.rstrip() + f"\n\n{replacement}"

        self._current_file.write_text(new_content.strip() + "\n", encoding="utf-8")

    def append(self, content: str) -> None:
        """Append user input to 待整理 section. No LLM involved."""
        existing_section = self._get_section("待整理")
        new_section = existing_section + f"\n- {content.strip()}" if existing_section else f"- {content.strip()}"
        self._set_section("待整理", new_section)
        if self.status == PlanStatus.EMPTY:
            self._set_status(PlanStatus.DRAFT)

    def set_planned(self, plan_content: str) -> None:
        """Opus has analyzed 待整理 and produced an ordered checklist.
        Clears 待整理, writes to 已規劃.
        """
        if self.status == PlanStatus.EMPTY:
            raise ValueError("沒有草稿可以規劃")
        self._set_section("已規劃", plan_content.strip())
        # Clear 待整理 since it's been processed
        content = self.read()
        content = re.sub(r"## 待整理\n.*?(?=\n## |\Z)", "", content, flags=re.DOTALL).strip()
        if content:
            self._current_file.write_text(content + "\n", encoding="utf-8")
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
        """Mark a checklist item as done and move to 已完成."""
        content = self.read()
        lines = content.split("\n")
        completed_line = None
        for i, line in enumerate(lines):
            if "- [ ]" in line and item_substring in line:
                completed_line = line.replace("- [ ]", "- [x]", 1)
                lines[i] = ""  # Remove from 已規劃
                break

        # Write back without the completed line
        content = "\n".join(line for line in lines if line is not None).strip()
        self._current_file.write_text(content + "\n", encoding="utf-8")

        # Add to 已完成 section
        if completed_line:
            existing_completed = self._get_section("已完成")
            new_completed = existing_completed + f"\n{completed_line}" if existing_completed else completed_line
            self._set_section("已完成", new_completed)

    def all_completed(self) -> bool:
        """Check if all checklist items in 已規劃 are done."""
        planned = self._get_section("已規劃")
        return "- [ ]" not in planned

    def pending_items(self) -> list[str]:
        """Get list of uncompleted items from 已規劃."""
        planned = self._get_section("已規劃")
        return [
            line.strip()
            for line in planned.split("\n")
            if "- [ ]" in line
        ]

    def draft_items(self) -> list[str]:
        """Get list of items from 待整理."""
        draft = self._get_section("待整理")
        return [
            line.strip()
            for line in draft.split("\n")
            if line.strip().startswith("- ")
        ]

    def all_items_numbered(self) -> list[tuple[str, str, int]]:
        """Get all items with section name and index for deletion.
        Returns: [(section, line_text, global_index), ...]
        """
        items = []
        idx = 0
        for section in ("待整理", "已規劃", "已完成"):
            section_content = self._get_section(section)
            for line in section_content.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    idx += 1
                    items.append((section, line, idx))
        return items

    def delete_item(self, index: int) -> str | None:
        """Delete an item by its global index. Returns deleted text or None."""
        items = self.all_items_numbered()
        target = None
        for section, line, idx in items:
            if idx == index:
                target = (section, line)
                break
        if not target:
            return None

        section_name, line_text = target
        section_content = self._get_section(section_name)
        lines = section_content.split("\n")
        new_lines = [l for l in lines if l.strip() != line_text]
        new_section = "\n".join(new_lines).strip()

        if new_section:
            self._set_section(section_name, new_section)
        else:
            # Remove empty section
            content = self.read()
            content = re.sub(
                rf"## {re.escape(section_name)}\n.*?(?=\n## |\Z)",
                "", content, flags=re.DOTALL
            ).strip()
            if content:
                self._current_file.write_text(content + "\n", encoding="utf-8")
            else:
                self._current_file.unlink(missing_ok=True)

        self._update_status_from_content()
        return line_text

    def archive_completed(self) -> str:
        """Archive completed items + full snapshot. Keep pending in current.
        Returns archived content.
        """
        content = self.read()
        if not content:
            return ""

        # Full snapshot for archive
        today = date.today().isoformat()
        ts = datetime.now().strftime("%H%M%S")
        archive_file = self._archive_dir / f"{today}-{ts}.md"
        archive_file.write_text(
            f"# Archived Plan ({today})\n\n{content}\n",
            encoding="utf-8",
        )

        # Get completed text for return value
        completed = self._get_section("已完成")

        # Remove 已完成 section from current
        new_content = re.sub(
            r"\n*## 已完成\n.*?(?=\n## |\Z)",
            "", content, flags=re.DOTALL
        ).strip()

        # Check what's left
        if new_content and new_content != f"# Plan ({today})":
            self._current_file.write_text(new_content + "\n", encoding="utf-8")
            self._update_status_from_content()
        else:
            self._current_file.unlink(missing_ok=True)
            self._status_file.unlink(missing_ok=True)

        return completed

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
            return (
                f"[計畫草稿 — 尚未規劃]\n"
                f"{content}\n"
                f"[/計畫草稿]\n\n"
            )
