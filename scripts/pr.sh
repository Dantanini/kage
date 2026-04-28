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

# Auto-generate a PR body unless the caller already supplied one
HAS_BODY=false
for arg in "${GH_ARGS[@]}"; do
    case "$arg" in
        --body|-b|--body-file|-F|--fill)
            HAS_BODY=true
            break
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$HAS_BODY" = false ]; then
    BODY=$(python3 "$SCRIPT_DIR/pr_body.py" 2>/dev/null || echo "(auto body generation failed)")
    GH_ARGS+=("--body" "$BODY")
fi

if [ "$DRY_RUN" = true ]; then
    echo "gh pr create --base develop ${GH_ARGS[*]:-}"
    exit 0
fi

# Push if needed
git push -u origin "$BRANCH" 2>/dev/null || true

# Open PR with --base develop enforced
exec gh pr create --base develop "${GH_ARGS[@]}"
