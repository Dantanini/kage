#!/usr/bin/env python3
"""Generate a PR body from git commits + diff stats relative to a base ref.

Used by scripts/pr.sh when the user did not provide --body / --body-file / --fill.
The output is intentionally simple markdown so PRs always have *some* description.

Usage:
    python3 scripts/pr_body.py                  # base = origin/develop
    python3 scripts/pr_body.py origin/main      # custom base
"""

import subprocess
import sys


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        args, capture_output=True, text=True
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_commits(base_ref: str = "origin/develop") -> str:
    return _run_git([
        "git", "log", "--reverse", "--pretty=format:- %s", f"{base_ref}..HEAD"
    ])


def get_diff_stats(base_ref: str = "origin/develop") -> str:
    return _run_git([
        "git", "diff", "--stat", f"{base_ref}..HEAD"
    ])


def generate_body(base_ref: str = "origin/develop") -> str:
    commits = get_commits(base_ref)
    stats = get_diff_stats(base_ref)

    parts = []
    if commits:
        parts.append(f"## Changes\n\n{commits}")
    if stats:
        parts.append(f"## Diff stats\n\n```\n{stats}\n```")

    if not parts:
        return f"(no commits or diff vs {base_ref})"
    return "\n\n".join(parts)


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/develop"
    print(generate_body(base))


if __name__ == "__main__":
    main()
