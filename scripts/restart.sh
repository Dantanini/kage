#!/bin/sh
# 重啟 kage bot（確保只有一個 instance）

# Kill any rogue manual processes
pgrep -f "python3 bot.py" | while read pid; do
    # Don't kill the systemd-managed one (it will be restarted by systemctl)
    UNIT=$(ps -p "$pid" -o unit= 2>/dev/null)
    if [ "$UNIT" != "kage.service" ]; then
        echo "Killing rogue bot process: $pid"
        kill -9 "$pid" 2>/dev/null
    fi
done

sleep 1

# Mark that restart was NOT initiated via /restart (no memory save)
touch "$HOME/kage/.needs_recovery"

systemctl --user restart kage
sleep 2
systemctl --user status kage --no-pager | head -5
