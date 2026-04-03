#!/bin/bash
# branch_guard.sh — Block commits on protected branches.
# Usage: branch_guard.sh [branch_name]
#   If branch_name is provided, use it (for testing).
#   Otherwise, detect from git.

PROTECTED_BRANCHES="main develop"

if [ -n "$1" ]; then
    BRANCH="$1"
else
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
fi

for protected in $PROTECTED_BRANCHES; do
    if [ "$BRANCH" = "$protected" ]; then
        echo "❌ 禁止在 $BRANCH 上直接 commit。請切到 feature branch。"
        echo "   git checkout -b feat/your-feature"
        exit 1
    fi
done

exit 0
