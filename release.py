#!/usr/bin/env python3
"""release.py — Generate and create a PR from develop → main.

Pure logic for commit parsing and PR content generation.
CLI entry point calls `gh pr create`.

Usage:
    python3 release.py          # Create PR
    python3 release.py --dry-run  # Preview title and body only
"""

import re
import subprocess
import sys


# --- Commit type display order and labels ---

TYPE_ORDER = ["feat", "fix", "refactor", "docs", "ci", "chore", "other"]
TYPE_LABELS = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "refactor": "Refactoring",
    "docs": "Documentation",
    "ci": "CI",
    "chore": "Chores",
    "other": "Other",
}

# Conventional commit pattern: hash type(scope): description
_CC_RE = re.compile(
    r"^(?P<hash>[0-9a-f]+)\s+"
    r"(?P<type>\w+)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r":\s*"
    r"(?P<desc>.+)$"
)

_MERGE_RE = re.compile(r"^[0-9a-f]+\s+Merge ", re.IGNORECASE)


def parse_commits(log_output: str) -> list[dict]:
    """Parse git log --oneline output into structured commit data.

    Returns list of dicts with keys: hash, type, scope, description.
    Skips merge commits.
    """
    commits = []
    for line in log_output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if _MERGE_RE.match(line):
            continue

        m = _CC_RE.match(line)
        if m:
            commits.append({
                "hash": m.group("hash"),
                "type": m.group("type"),
                "scope": m.group("scope"),  # None if no scope
                "description": m.group("desc"),
            })
        else:
            # Non-conventional commit
            parts = line.split(maxsplit=1)
            commits.append({
                "hash": parts[0],
                "type": "other",
                "scope": None,
                "description": parts[1] if len(parts) > 1 else "",
            })
    return commits


def generate_title(commits: list[dict]) -> str:
    """Generate a concise PR title from parsed commits.

    Single commit: "Release: <type>: <description>"
    Multiple: "Release: N feat, M fix, ..." (top types only)
    """
    if not commits:
        return "Release"

    if len(commits) == 1:
        c = commits[0]
        title = f"Release: {c['type']}: {c['description']}"
        return title[:72]

    # Count by type
    counts: dict[str, int] = {}
    for c in commits:
        counts[c["type"]] = counts.get(c["type"], 0) + 1

    # Build summary in display order, skip types with 0
    parts = []
    for t in TYPE_ORDER:
        if t in counts:
            parts.append(f"{counts[t]} {t}")
    # Include any types not in TYPE_ORDER
    for t in counts:
        if t not in TYPE_ORDER:
            parts.append(f"{counts[t]} {t}")

    title = f"Release: {', '.join(parts)}"
    if len(title) > 72:
        # Truncate to top 2 types
        title = f"Release: {', '.join(parts[:2])}, +{len(parts) - 2} more"
    return title[:72]


def generate_body(commits: list[dict]) -> str:
    """Generate PR body with changelog grouped by type."""
    if not commits:
        return ""

    # Group by type
    groups: dict[str, list[dict]] = {}
    for c in commits:
        groups.setdefault(c["type"], []).append(c)

    sections = []
    for t in TYPE_ORDER:
        if t not in groups:
            continue
        label = TYPE_LABELS.get(t, t.capitalize())
        lines = [f"## {label}"]
        for c in groups[t]:
            lines.append(f"- {c['description']} (`{c['hash']}`)")
        sections.append("\n".join(lines))

    # Any types not in TYPE_ORDER
    for t in groups:
        if t not in TYPE_ORDER:
            label = t.capitalize()
            lines = [f"## {label}"]
            for c in groups[t]:
                lines.append(f"- {c['description']} (`{c['hash']}`)")
            sections.append("\n".join(lines))

    return "\n\n".join(sections)


def get_commits_between(base: str = "main", head: str = "develop") -> str:
    """Get git log --oneline between two remote branches.

    Uses origin/ prefix to compare remote refs (requires git fetch first).
    """
    result = subprocess.run(
        ["git", "log", "--oneline", f"origin/{base}..origin/{head}"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def create_pr(title: str, body: str, base: str = "main", head: str = "develop"):
    """Create PR via gh CLI."""
    subprocess.run(
        ["gh", "pr", "create",
         "--base", base,
         "--head", head,
         "--title", title,
         "--body", body],
        check=True,
    )


def sync_develop_with_main():
    """Sync develop with main after the release PR has been merged.

    Brings main's merge commit (and any direct fixes on main) back into
    develop so future feature branches start from up-to-date history.
    Run this after the GitHub PR is merged.
    """
    subprocess.run(["git", "fetch", "origin"], check=True)
    subprocess.run(["git", "checkout", "develop"], check=True)
    subprocess.run(["git", "pull", "origin", "develop"], check=True)
    subprocess.run(["git", "merge", "origin/main", "--no-edit"], check=True)
    subprocess.run(["git", "push", "origin", "develop"], check=True)


def main():
    if "--sync" in sys.argv:
        sync_develop_with_main()
        print("✅ develop synced with main")
        return

    dry_run = "--dry-run" in sys.argv

    # Fetch latest
    subprocess.run(["git", "fetch", "origin"], check=True)

    log_output = get_commits_between()
    if not log_output:
        print("No commits between main and develop. Nothing to release.")
        sys.exit(0)

    commits = parse_commits(log_output)
    title = generate_title(commits)
    body = generate_body(commits)

    print(f"Title: {title}")
    print(f"\n{body}")

    if dry_run:
        print("\n(dry-run mode, PR not created)")
        return

    create_pr(title, body)
    print("\nPR created!")
    print("\n📝 Merge 完成後請跑：python3 release.py --sync  (把 main 同步回 develop)")


if __name__ == "__main__":
    main()
