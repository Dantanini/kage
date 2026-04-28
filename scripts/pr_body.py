#!/usr/bin/env python3
"""Generate a PR body from git commits + diff stats relative to a base ref.

Used by scripts/pr.sh when the user did not provide --body / --body-file / --fill.
The output is intentionally simple markdown so PRs always have *some* description.

Includes a sanitizer (`scan_for_sensitive`) that hard-fails if the generated
body would leak personal/sensitive data — kage PRs are public-facing, so they
must only describe functionality, never private context.

Usage:
    python3 scripts/pr_body.py                  # base = origin/develop
    python3 scripts/pr_body.py origin/main      # custom base
"""

import re
import subprocess
import sys


# --- Sensitive patterns ---
# Anything that matches these MUST NOT appear in a kage PR body.
# Add patterns here when new leak vectors are discovered.
SENSITIVE_PATTERNS: dict[str, str] = {
    # Real tokens / secrets
    "telegram_bot_token": r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b",
    "anthropic_key": r"\bsk-ant-[A-Za-z0-9_-]{20,}\b",
    "openai_key": r"\bsk-[A-Za-z0-9]{20,}\b",
    "github_token": r"\b(ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9]{20,}\b",
    "gitlab_token": r"\bglpat-[A-Za-z0-9_-]{20,}\b",
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    # Personal / family names (kage is open source-ish; family stays private)
    "family_names": r"(邱邱|小元寶|王欣元)",
    # Personal context paths from sibling repo (dev-journal).
    # No \b boundaries: the patterns contain non-word chars (/, -) where \b
    # behaves unintuitively, and these strings are specific enough to not need
    # boundary protection.
    "personal_dirs": r"(interview/|profile/|work-history/|threads-farm|"
                     r"couple-dynamics|mental-health|family-routing|"
                     r"complete-profile|關係圖譜|經歷更新|面試練習)",
    # Career / recruiting names
    "recruiting_targets": r"\b(CMoney|TWJOIN|Seekrtech|多奇)\b",
    # Local absolute paths revealing username
    "user_paths": r"/(home|Users)/[a-z][a-z0-9_-]+/",
}


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


def scan_for_sensitive(text: str) -> list[tuple[str, list[str]]]:
    """Return [(label, matches), ...] for any sensitive pattern hits in `text`.

    Empty list = clean. Used by generate_body() and by pr.sh to hard-fail
    if the PR body would leak personal/sensitive data.
    """
    hits = []
    for label, pattern in SENSITIVE_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            # findall may return tuples for groups; normalise to strings
            flat = [m if isinstance(m, str) else next((g for g in m if g), "") for m in matches]
            hits.append((label, sorted(set(flat))))
    return hits


class SensitiveContentError(RuntimeError):
    """Raised when generated PR body contains sensitive information."""


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/develop"
    body = generate_body(base)

    hits = scan_for_sensitive(body)
    if hits:
        # Print to stderr so the calling script can detect failure
        print(
            "ERROR: PR body contains sensitive content. Refusing to output.\n"
            "Detected:",
            file=sys.stderr,
        )
        for label, matches in hits:
            print(f"  - {label}: {matches}", file=sys.stderr)
        print(
            "\nFix: rewrite commit messages or pass --body explicitly with "
            "sanitized text. See scripts/pr_body.py SENSITIVE_PATTERNS.",
            file=sys.stderr,
        )
        sys.exit(2)

    print(body)


if __name__ == "__main__":
    main()
