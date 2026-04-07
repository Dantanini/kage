#!/usr/bin/env python3
"""Git add + commit（不 push）。用法: python commit.py "commit message"

kage 走 PR flow，commit 後請手動開 PR 或用 scripts/pr.sh。
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)


def main():
    if len(sys.argv) < 2:
        print("用法: python commit.py \"commit message\"")
        sys.exit(1)

    message = sys.argv[1]

    # Check if there are changes
    status = run(["git", "status", "--porcelain"])
    if not status.stdout.strip():
        print("沒有變更需要 commit")
        return

    # Branch guard: block commits on main
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch_name = branch.stdout.strip()
    print(f"目前分支: {branch_name}")

    if branch_name == "main":
        print("❌ 禁止在 main 上直接 commit。請切到 feature branch。")
        print("   git checkout -b feat/your-feature develop")
        sys.exit(1)

    # Stage all changes
    result = run(["git", "add", "-A"])
    if result.returncode != 0:
        print(f"git add 失敗: {result.stderr}")
        sys.exit(1)

    # Commit
    result = run(["git", "commit", "-m", message])
    if result.returncode != 0:
        print(f"git commit 失敗: {result.stderr}")
        sys.exit(1)
    print(result.stdout.strip())
    print("已 commit（未 push）— 用 scripts/pr.sh 開 PR")


if __name__ == "__main__":
    main()
