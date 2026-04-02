# kage 專案規範

## 操作規則

- 重啟 bot → 執行 `bash scripts/restart.sh`，不要手打 systemctl
- 看 log → 執行 `journalctl --user -u kage -f`
- 停止 bot → 執行 `systemctl --user stop kage`
- 不要用 nohup / & 手動啟動 bot，一律走 systemd
- **禁止在對話中直接執行 `restart.sh` 或 `systemctl restart`** — 必須告訴使用者用 `/restart` 指令，這樣 bot 才能先儲存記憶再重啟

## 開發流程

- **TDD 優先**：新增功能或修改核心邏輯時，先寫 test case 再實作。不接受先寫功能後補 test。
  - 流程：定義 test cases → 實作 tests → 寫 code pass tests → refactor
  - 如果使用者直接要求「幫我寫 XXX 功能」，先問「要不要先定義 test cases？」
  - 純 config 變更、文件更新不需要 test
- **跑測試後才 commit**：commit 前必須先跑 test，全過才 commit
- **commit message 用英文**，conventional commits 格式（feat/fix/docs/refactor/chore），方便未來搜尋

## 工程原則

- 確定性操作用腳本，不手打指令
- 機敏資訊（token, ID）只放 .env，不進程式碼
- 所有 commit 前經過 3 層 secret 掃描（.githooks/pre-commit）
- 絕不做破壞性 git 操作（force push, rm -rf .git）
- 能用設計約束的就不要靠紀律約束
