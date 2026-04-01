#!/usr/bin/env bash
# deploy-develop.sh — 一鍵測試 + 分 commit + push
# 使用方式: 在 kage 目錄下執行 bash scripts/deploy-develop.sh
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== kage develop branch deploy ===${NC}"
echo ""

# 0. 確認在 develop branch
BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "develop" ]; then
    echo -e "${RED}ERROR: 不在 develop branch (目前: $BRANCH)${NC}"
    echo "請先執行: git checkout develop"
    exit 1
fi
echo -e "${GREEN}✓ 在 develop branch${NC}"

# 1. 安裝 test 依賴
echo ""
echo -e "${YELLOW}[1/5] 安裝 test 依賴...${NC}"
pip install pytest pytest-asyncio --quiet --break-system-packages 2>/dev/null || \
pip install pytest pytest-asyncio --quiet

# 2. 跑測試
echo ""
echo -e "${YELLOW}[2/5] 跑測試...${NC}"
if ! pytest tests/ -v --tb=short; then
    echo ""
    echo -e "${RED}✗ 測試失敗！請修復後再 deploy${NC}"
    exit 1
fi
echo ""
echo -e "${GREEN}✓ 全部測試通過${NC}"

# 3. 分 commit
echo ""
echo -e "${YELLOW}[3/5] 建立 commits...${NC}"

# Commit 1: Session hooks
git add session.py tests/test_session.py pyproject.toml
git commit -m "feat: add session lifecycle hook system

- SessionHook type with async start/end hooks
- Hooks run once on start, every time on end
- Failing hooks don't block others
- SessionManager registers hook factories for all new sessions
- close() is now async to support end hooks
- git pull auto-runs on session start" || echo "  (session hooks: nothing to commit)"

# Commit 2: Persistent memory
git add memory.py tests/test_memory.py
git commit -m "feat: add persistent memory layer

- MemoryStore reads/writes markdown memory file
- Memory injected into every new prompt as context prefix
- Session end hook auto-saves important context via Claude
- Inspired by Claude Code memdir/autoDream architecture" || echo "  (memory: nothing to commit)"

# Commit 3: Workflow chains + bot.py integration
git add workflows.py tests/test_workflows.py bot.py requirements.txt
git commit -m "feat: replace monolithic prompts with code-defined workflow chains

- WorkflowStep/WorkflowResult data classes
- run_workflow() executes steps sequentially with context forwarding
- Gather steps use sonnet (cheap), synthesis uses opus (smart)
- Chain stops on failure with partial results
- /morning and /evening both migrated to workflow system
- handle_callback also uses workflows" || echo "  (workflows: nothing to commit)"

# Commit 4: CI
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions test workflow

- Runs pytest on push to main/develop and on PRs
- Python 3.12, ubuntu-latest" || echo "  (ci: nothing to commit)"

# Commit 5: Deploy script itself
git add scripts/deploy-develop.sh
git commit -m "chore: add one-click deploy script for develop branch" || echo "  (deploy script: nothing to commit)"

echo -e "${GREEN}✓ Commits 建立完成${NC}"

# 4. 顯示 commit log
echo ""
echo -e "${YELLOW}[4/5] 最近的 commits:${NC}"
git log --oneline -6

# 5. Push
echo ""
echo -e "${YELLOW}[5/5] Push 到 origin/develop...${NC}"
git push origin develop

echo ""
echo -e "${GREEN}=== 部署完成！===${NC}"
echo ""
echo "下一步："
echo "  1. 去 GitHub 看 CI 是否綠燈: https://github.com/Dantanini/kage/actions"
echo "  2. 在 VPS 上 pull 並重啟 bot:"
echo "     cd ~/tg-bot && git pull && bash scripts/restart.sh"
echo "  3. 測試 /morning 和 /done 是否正常運作"
