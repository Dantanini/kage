"""PlanStore v2 — three-file plan management, no LLM needed.

Three separate files, program-controlled read/write boundaries:
  draft.md      — user's raw input (pure append, LLM never touches)
  planned.md    — Opus-produced ordered checklist (LLM reads for execution)
  completed.md  — finished items (program moves here, LLM never touches)

Stored in .local/plan/ (git-ignored) to avoid leaking private content.
"""

import logging
import shutil
from datetime import date, datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PlanStatus(Enum):
    EMPTY = "empty"
    DRAFT = "draft"
    PLANNED = "planned"
    EXECUTING = "executing"


PLAN_INSTRUCTIONS = """\
## Instructions
- 每個 task 開獨立 feature branch from develop
- commit 前必須 `git branch --show-current` 確認不在 main/develop
- 完成一個 task 後等待 bot 發下一個，不要自行跳到下一項
- **不要直接開 PR**，等用戶在 TG 按「開 PR」按鈕
- PR 一律透過 `scripts/pr.sh` 開，寫死 `--base develop`
"""


def _read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n" if content.strip() else "", encoding="utf-8")


def _clear_file(path: Path) -> None:
    if path.exists():
        path.write_text("", encoding="utf-8")


class PlanStore:
    """Manages plan lifecycle with three separate files."""

    def __init__(self, local_dir: str):
        self._local_dir = local_dir
        self._plan_dir = Path(local_dir) / "plan"
        self._plan_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir = self._plan_dir / "archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _draft_file(self) -> Path:
        return self._plan_dir / "draft.md"

    @property
    def _planned_file(self) -> Path:
        return self._plan_dir / "planned.md"

    @property
    def _completed_file(self) -> Path:
        return self._plan_dir / "completed.md"

    @property
    def _status_file(self) -> Path:
        return self._plan_dir / "status"

    # ── Status ──

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
        has_planned = bool(self.pending_items())
        has_draft = bool(self.draft_items())
        if has_planned:
            if self.status != PlanStatus.EXECUTING:
                self._set_status(PlanStatus.PLANNED)
        elif has_draft:
            self._set_status(PlanStatus.DRAFT)
        else:
            self._status_file.unlink(missing_ok=True)

    def has_plan(self) -> bool:
        return (
            bool(_read_file(self._draft_file))
            or bool(_read_file(self._planned_file))
            or bool(_read_file(self._completed_file))
        )

    # ── Read ──

    def read_draft(self) -> str:
        return _read_file(self._draft_file)

    def read_planned(self) -> str:
        return _read_file(self._planned_file)

    def read_completed(self) -> str:
        return _read_file(self._completed_file)

    def read(self) -> str:
        """Read all three files combined (for display)."""
        parts = []
        draft = self.read_draft()
        planned = self.read_planned()
        completed = self.read_completed()
        if draft:
            parts.append(f"## 待整理\n{draft}")
        if planned:
            parts.append(f"## 已規劃\n{planned}")
        if completed:
            parts.append(f"## 已完成\n{completed}")
        return "\n\n".join(parts)

    # ── Write ──

    def append(self, content: str) -> None:
        """Append to draft.md. No LLM involved."""
        existing = _read_file(self._draft_file)
        new_line = f"- {content.strip()}"
        new_content = f"{existing}\n{new_line}" if existing else new_line
        _write_file(self._draft_file, new_content)
        if self.status == PlanStatus.EMPTY:
            self._set_status(PlanStatus.DRAFT)

    def set_planned(self, plan_content: str) -> None:
        """Write Opus output to planned.md, clear draft.md."""
        if self.status == PlanStatus.EMPTY:
            raise ValueError("沒有草稿可以規劃")
        _write_file(self._planned_file, plan_content)
        _clear_file(self._draft_file)
        self._set_status(PlanStatus.PLANNED)

    def set_executing(self) -> None:
        if self.status not in (PlanStatus.PLANNED,):
            raise ValueError("沒有計畫可以執行")
        self._set_status(PlanStatus.EXECUTING)

    def pause(self) -> None:
        self._set_status(PlanStatus.PLANNED)

    def complete_item(self, item_substring: str, branch: str | None = None) -> None:
        """Move a matching item from planned.md to completed.md.
        Optionally record the branch name for later PR opening.
        """
        planned = _read_file(self._planned_file)
        lines = planned.split("\n")
        completed_line = None

        new_lines = []
        for line in lines:
            if completed_line is None and "- [ ]" in line and item_substring in line:
                completed_line = line.replace("- [ ]", "- [x]", 1)
                if branch and f"branch: {branch}" not in completed_line:
                    completed_line += f" — branch: {branch}"
            else:
                new_lines.append(line)

        _write_file(self._planned_file, "\n".join(new_lines))

        if completed_line:
            existing_completed = _read_file(self._completed_file)
            new_completed = f"{existing_completed}\n{completed_line}" if existing_completed else completed_line
            _write_file(self._completed_file, new_completed)

    def all_completed(self) -> bool:
        planned = _read_file(self._planned_file)
        return "- [ ]" not in planned

    def pending_items(self) -> list[str]:
        planned = _read_file(self._planned_file)
        return [l.strip() for l in planned.split("\n") if "- [ ]" in l]

    def draft_items(self) -> list[str]:
        draft = _read_file(self._draft_file)
        return [l.strip() for l in draft.split("\n") if l.strip().startswith("- ")]

    def completed_branches(self) -> list[str]:
        """Extract branch names from completed items."""
        completed = _read_file(self._completed_file)
        branches = []
        for line in completed.split("\n"):
            parsed = self._parse_item_metadata(line)
            if parsed.get("branch"):
                branches.append(parsed["branch"])
        return branches

    def parse_planned_items(self) -> list[dict]:
        """Parse planned.md items into structured dicts.
        Returns: [{"task": str, "branch": str|None, "repo": str|None}, ...]
        """
        planned = _read_file(self._planned_file)
        items = []
        for line in planned.split("\n"):
            line = line.strip()
            if not line.startswith("- [ ]"):
                continue
            parsed = self._parse_item_metadata(line)
            items.append(parsed)
        return items

    def current_item_index(self) -> int | None:
        """Get index of the first pending item, or None if all done."""
        pending = self.pending_items()
        return 0 if pending else None

    @staticmethod
    def _parse_item_metadata(line: str) -> dict:
        """Parse a checklist line into {task, branch, repo}.
        Format: - [ ] task description — branch: xxx, repo: yyy
        """
        # Strip checkbox prefix
        text = line.strip()
        for prefix in ("- [ ] ", "- [x] "):
            if text.startswith(prefix):
                text = text[len(prefix):]
                break

        # Split on " — " to separate task from metadata
        parts = text.split(" — ", 1)
        task = parts[0].strip().rstrip("*").strip()
        branch = None
        repo = None

        if len(parts) > 1:
            metadata = parts[1]
            import re
            branch_match = re.search(r"branch:\s*`?([^\s,`]+)`?", metadata)
            repo_match = re.search(r"repo:\s*`?([^\s,`]+)`?", metadata)
            if branch_match:
                branch = branch_match.group(1)
            if repo_match:
                repo = repo_match.group(1)

        return {"task": task, "branch": branch, "repo": repo}

    # ── Delete ──

    def all_items_numbered(self) -> list[tuple[str, str, int]]:
        """Returns [(file_type, line_text, global_index), ...]"""
        items = []
        idx = 0
        for file_type, path in [("draft", self._draft_file), ("planned", self._planned_file), ("completed", self._completed_file)]:
            content = _read_file(path)
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    idx += 1
                    items.append((file_type, line, idx))
        return items

    def delete_item(self, index: int) -> str | None:
        target = None
        for file_type, line, idx in self.all_items_numbered():
            if idx == index:
                target = (file_type, line)
                break
        if not target:
            return None

        file_type, line_text = target
        path = {"draft": self._draft_file, "planned": self._planned_file, "completed": self._completed_file}[file_type]
        content = _read_file(path)
        lines = content.split("\n")
        new_lines = [l for l in lines if l.strip() != line_text]
        _write_file(path, "\n".join(new_lines))
        self._update_status_from_content()
        return line_text

    # ── Archive ──

    def archive_completed(self) -> str:
        """Archive all three files as snapshot, clear completed.md."""
        completed = self.read_completed()

        # Create snapshot directory
        today = date.today().isoformat()
        ts = datetime.now().strftime("%H%M%S")
        snapshot_dir = self._archive_dir / f"{today}-{ts}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Copy all files to snapshot
        for src in (self._draft_file, self._planned_file, self._completed_file):
            if src.exists() and _read_file(src):
                shutil.copy2(src, snapshot_dir / src.name)

        # Clear completed
        _clear_file(self._completed_file)

        # Update status
        self._update_status_from_content()
        return completed

    # ── Context injection ──

    def build_context_injection(self) -> str:
        if self.status == PlanStatus.EMPTY:
            return ""

        if self.status in (PlanStatus.PLANNED, PlanStatus.EXECUTING):
            planned = self.read_planned()
            return (
                f"[Session 計畫]\n"
                f"{PLAN_INSTRUCTIONS}\n"
                f"{planned}\n"
                f"[/Session 計畫]\n\n"
            )
        else:
            draft = self.read_draft()
            return (
                f"[計畫草稿 — 尚未規劃]\n"
                f"{draft}\n"
                f"[/計畫草稿]\n\n"
            )
