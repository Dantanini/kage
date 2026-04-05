# kage 專案規範

## 操作規則

- 重啟 bot → 執行 `bash scripts/restart.sh`，不要手打 systemctl
- 看 log → 執行 `journalctl --user -u kage -f`
- 停止 bot → 執行 `systemctl --user stop kage`
- 不要用 nohup / & 手動啟動 bot，一律走 systemd
- **禁止在對話中直接執行 `restart.sh` 或 `systemctl restart`** — 必須告訴使用者用 `/restart` 指令，這樣 bot 才能先儲存記憶再重啟

## 分支策略

採用 GitHub Flow + develop 分支，適合 solo/小團隊且需要 staging 的專案。

```
feature/* or fix/*  →  PR to develop  →  /release  →  PR to main
```

### 規則

- `main`：production，只接受從 `develop` 來的 PR（透過 release.py）
- `develop`：staging，接受所有 feature/fix PR
- **開 PR 一律 base `develop`，禁止直接開到 `main`**
- 新功能分支從 `develop` 切出：`git checkout -b feat/xxx develop`
- 修復分支從 `develop` 切出：`git checkout -b fix/xxx develop`
- Release 流程由使用者手動呼叫 `/release`，不要自己執行 release.py
- 合併後的 feature/fix 分支由使用者決定是否刪除

### 分支前綴

| 前綴 | 用途 |
|---|---|
| `feat/` | 新功能 |
| `fix/` | Bug 修復 |
| `refactor/` | 重構（不改變行為） |
| `chore/` | 工具、CI、依賴更新等 |

小改動（docs 更新、typo 修正）不需要開分支，直接在 `develop` commit。

### 為什麼不用完整 Git Flow

Solo 專案不需要 `release/*`、`hotfix/*`。多一層分支 = 多一層出錯機會，沒有對應的收益。

## 開發流程

- **TDD 優先**：新增功能或修改核心邏輯時，先寫 test case 再實作。不接受先寫功能後補 test。
  - 流程：定義 test cases → 實作 tests → 寫 code pass tests → refactor
  - 如果使用者直接要求「幫我寫 XXX 功能」，先問「要不要先定義 test cases？」
  - 純 config 變更、文件更新不需要 test
- **跑測試後才 commit**：commit 前必須先跑 test，全過才 commit
- **commit message 用英文**，conventional commits 格式（feat/fix/docs/refactor/chore），方便未來搜尋

## 測試隔離

- 測試如果涉及 git 指令或檔案系統寫入，必須 mock 或使用 `tmp_path`，**禁止直接操作 working tree**
- 原因：曾發生 test 跑 `git checkout main` 刪掉 develop-only 檔案，汙染後續 test（PR #39）

## 工具使用規則

- commit → `python3 scripts/commit.py "message"`，禁止直接跑 `git commit`
- 開 PR → `bash scripts/pr.sh`，禁止直接跑 `gh pr create`

## 工程原則

- 確定性操作用腳本，不手打指令
- 機敏資訊（token, ID）只放 .env，不進程式碼
- 所有 commit 前經過 3 層 secret 掃描（.githooks/pre-commit）
- 絕不做破壞性 git 操作（force push, rm -rf .git）
- 能用設計約束的就不要靠紀律約束
