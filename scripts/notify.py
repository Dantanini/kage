#!/usr/bin/env python3
"""定時通知 — cron 呼叫，發帶按鈕的訊息給 Dante。

用法:
  python3 notify.py morning
  python3 notify.py evening
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "")

NOTIFICATIONS = {
    "morning": {
        "text": "🌅 早安！要看今天的主線建議嗎？",
        "button_text": "查看今日主線",
        "callback": "morning",
    },
    "evening": {
        "text": "🌙 辛苦了！要整理今天的日結嗎？",
        "button_text": "開始日結",
        "callback": "evening",
    },
}


def send(kind: str):
    notif = NOTIFICATIONS[kind]
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": int(ADMIN_ID),
        "text": notif["text"],
        "reply_markup": {
            "inline_keyboard": [[{
                "text": notif["button_text"],
                "callback_data": notif["callback"],
            }]]
        },
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in NOTIFICATIONS:
        print(f"用法: python3 notify.py [{'/'.join(NOTIFICATIONS.keys())}]")
        sys.exit(1)

    kind = sys.argv[1]
    send(kind)
    print(f"已發送 {kind} 通知")


if __name__ == "__main__":
    main()
