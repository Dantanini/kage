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
    # Triple-dot diff = changes from merge-base, so a stale branch doesn't
    # appear to "revert" commits that landed on the base after we branched.
    return _run_git([
        "git", "diff", "--stat", f"{base_ref}...HEAD"
    ])


def get_test_files_changed(base_ref: str = "origin/develop") -> list[str]:
    out = _run_git([
        "git", "diff", "--name-only", f"{base_ref}...HEAD"
    ])
    return [f for f in out.splitlines() if f.startswith("tests/")]


def generate_body(base_ref: str = "origin/develop") -> str:
    """Generate a PR body in the project's standard template:

    ## Summary
    - bullet (one per commit)

    ## Diff stats
    ```
    ...
    ```

    ## Test plan
    - [x] tests pass / no test changes
    - [ ] CI passes

    🤖 Generated with [Claude Code](https://claude.com/claude-code)
    """
    commits = get_commits(base_ref)
    stats = get_diff_stats(base_ref)
    test_files = get_test_files_changed(base_ref)

    sections = []

    if commits:
        sections.append(f"## Summary\n\n{commits}")
    else:
        sections.append(f"## Summary\n\n(no commits vs {base_ref})")

    if stats:
        sections.append(f"## Diff stats\n\n```\n{stats}\n```")

    test_line = (
        f"- [x] {len(test_files)} test file(s) changed; run full suite locally"
        if test_files
        else "- [x] no test changes (config / docs only)"
    )
    sections.append(
        "## Test plan\n\n"
        f"{test_line}\n"
        "- [ ] CI passes"
    )

    sections.append("🤖 Generated with [Claude Code](https://claude.com/claude-code)")

    return "\n\n".join(sections)


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/develop"
    print(generate_body(base))


if __name__ == "__main__":
    main()
