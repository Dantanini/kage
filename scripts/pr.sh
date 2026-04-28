#!/bin/bash
# pr.sh — Open PR with --base develop enforced.
# Usage: scripts/pr.sh [--dry-run] [--branch <name>] [-- <extra gh args>]
#
# --dry-run:        Print what would be run, don't execute
# --branch <name>:  Override branch detection (for testing)
# Extra args after -- are forwarded to gh pr create.

set -euo pipefail

DRY_RUN=false
BRANCH=""
GH_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --)
            shift
            GH_ARGS=("$@")
            break
            ;;
        *)
            GH_ARGS+=("$1")
            shift
            ;;
    esac
done

# Detect branch if not overridden
if [ -z "$BRANCH" ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
fi

# Block PRs from protected branches
PROTECTED="main develop"
for p in $PROTECTED; do
    if [ "$BRANCH" = "$p" ]; then
        echo "❌ 禁止從 $BRANCH 開 PR。請切到 feature branch。"
        exit 1
    fi
done

# Detect what the caller already supplied
HAS_BODY=false
HAS_TITLE=false
for arg in "${GH_ARGS[@]}"; do
    case "$arg" in
        --body|-b|--body-file|-F|--fill|--fill-first|--fillverbose)
            HAS_BODY=true
            ;;
        --title|-t|--fill|--fill-first|--fillverbose)
            HAS_TITLE=true
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Auto-generate a PR body unless the caller already supplied one
if [ "$HAS_BODY" = false ]; then
    # pr_body.py exits non-zero (and writes to stderr) if the auto-generated
    # body would leak sensitive info — refuse to open the PR in that case.
    if ! BODY=$(python3 "$SCRIPT_DIR/pr_body.py"); then
        echo "❌ 拒絕開 PR：自動生成的 body 含機敏資訊（見上方 stderr）。" >&2
        echo "   修法：改 commit message 或手動傳 --body \"...\"。" >&2
        exit 2
    fi
    GH_ARGS+=("--body" "$BODY")
fi

# Auto-generate a PR title from first commit on branch (vs origin/develop)
if [ "$HAS_TITLE" = false ]; then
    git fetch origin develop --quiet 2>/dev/null || true
    TITLE=$(git log --reverse --pretty=format:"%s" origin/develop..HEAD 2>/dev/null | head -1)
    if [ -z "$TITLE" ]; then
        TITLE=$(git log -1 --pretty=format:"%s" 2>/dev/null)
    fi
    if [ -n "$TITLE" ]; then
        GH_ARGS+=("--title" "$TITLE")
    fi
fi

if [ "$DRY_RUN" = true ]; then
    echo "gh pr create --base develop ${GH_ARGS[*]:-}"
    exit 0
fi

# Push if needed
git push -u origin "$BRANCH" 2>/dev/null || true

# Open PR with --base develop enforced
exec gh pr create --base develop "${GH_ARGS[@]}"
