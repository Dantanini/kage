# kage 專案規範

## 操作規則

- 重啟 bot → 執行 `bash scripts/restart.sh`，不要手打 systemctl
- 看 log → 執行 `journalctl --user -u kage -f`
- 停止 bot → 執行 `systemctl --user stop kage`
- 不要用 nohup / & 手動啟動 bot，一律走 systemd

## 工程原則

- 確定性操作用腳本，不手打指令
- 機敏資訊（token, ID）只放 .env，不進程式碼
- 所有 commit 前經過 3 層 secret 掃描（.githooks/pre-commit）
- 絕不做破壞性 git 操作（force push, rm -rf .git）

## systemd service

- 路徑：`~/.config/systemd/user/kage.service`
- Restart=always，crash 會自動重啟
- 改 service 檔後需 `systemctl --user daemon-reload`
