# deploy-develop.ps1 — 一鍵測試 + 分 commit + push (Windows PowerShell)
# 使用方式: 在 kage 目錄下執行 .\scripts\deploy-develop.ps1
$ErrorActionPreference = "Stop"

Write-Host "=== kage develop branch deploy ===" -ForegroundColor Yellow
Write-Host ""

# 0. 確認在 develop branch
$branch = git branch --show-current
if ($branch -ne "develop") {
    Write-Host "ERROR: 不在 develop branch (目前: $branch)" -ForegroundColor Red
    Write-Host "請先執行: git checkout develop"
    exit 1
}
Write-Host "✓ 在 develop branch" -ForegroundColor Green

# 1. 安裝 test 依賴
Write-Host ""
Write-Host "[1/5] 安裝 test 依賴..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
pip install pytest pytest-asyncio --quiet 2>&1 | Out-Null
$ErrorActionPreference = "Stop"

# 2. 跑測試
Write-Host ""
Write-Host "[2/5] 跑測試..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
pytest tests/ -v --tb=short
$testResult = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($testResult -ne 0) {
    Write-Host ""
    Write-Host "✗ 測試失敗！請修復後再 deploy" -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "✓ 全部測試通過" -ForegroundColor Green

# 3. 分 commit
Write-Host ""
Write-Host "[3/5] 建立 commits..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"

# Commit 1: Session hooks + fix encoding bug
git add session.py tests/test_session.py tests/test_router.py pyproject.toml 2>&1 | Out-Null
git commit -m "feat: add session lifecycle hook system" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Host "  ✓ Commit 1: session hooks" -ForegroundColor Green } else { Write-Host "  - Commit 1: nothing to commit" -ForegroundColor DarkGray }

# Commit 2: Persistent memory
git add memory.py tests/test_memory.py 2>&1 | Out-Null
git commit -m "feat: add persistent memory layer" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Host "  ✓ Commit 2: persistent memory" -ForegroundColor Green } else { Write-Host "  - Commit 2: nothing to commit" -ForegroundColor DarkGray }

# Commit 3: Workflow chains + bot.py integration
git add workflows.py tests/test_workflows.py bot.py requirements.txt 2>&1 | Out-Null
git commit -m "feat: replace monolithic prompts with code-defined workflow chains" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Host "  ✓ Commit 3: workflow chains" -ForegroundColor Green } else { Write-Host "  - Commit 3: nothing to commit" -ForegroundColor DarkGray }

# Commit 4: CI
git add .github/workflows/ci.yml 2>&1 | Out-Null
git commit -m "ci: add GitHub Actions test workflow" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Host "  ✓ Commit 4: CI" -ForegroundColor Green } else { Write-Host "  - Commit 4: nothing to commit" -ForegroundColor DarkGray }

# Commit 5: Deploy scripts
git add scripts/deploy-develop.sh scripts/deploy-develop.ps1 2>&1 | Out-Null
git commit -m "chore: add one-click deploy scripts for develop branch" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Host "  ✓ Commit 5: deploy scripts" -ForegroundColor Green } else { Write-Host "  - Commit 5: nothing to commit" -ForegroundColor DarkGray }

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "✓ Commits 建立完成" -ForegroundColor Green

# 4. 顯示 commit log
Write-Host ""
Write-Host "[4/5] 最近的 commits:" -ForegroundColor Yellow
git log --oneline -6

# 5. Push
Write-Host ""
Write-Host "[5/5] Push 到 origin/develop..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
git push origin develop 2>&1
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== 部署完成！===" -ForegroundColor Green
Write-Host ""
Write-Host "下一步："
Write-Host "  1. 去 GitHub 看 CI 是否綠燈: https://github.com/Dantanini/kage/actions"
Write-Host "  2. 在 VPS 上 pull 並重啟 bot:"
Write-Host "     cd ~/tg-bot && git pull origin develop && bash scripts/restart.sh"
Write-Host "  3. 測試 /morning 和 /done 是否正常運作"
