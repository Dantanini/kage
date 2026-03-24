#!/usr/bin/env python3
"""定時通知 — cron 呼叫，發訊息給 Dante 的 TG Bot。

用法:
  python3 notify.py morning
  python3 notify.py evening
"""

import asyncio
import os
import sys
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

MESSAGES = {
    "morning": "🌅 早安！輸入 /morning 看今天的主線建議",
    "evening": "🌙 辛苦了！輸入 /evening 整理今天的日結",
}


async def send(text: str):
    # Use raw HTTP to avoid importing telegram library (lighter for cron)
    import urllib.request
    import json

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = json.dumps({"chat_id": int(ADMIN_ID), "text": text}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in MESSAGES:
        print(f"用法: python3 notify.py [{'/'.join(MESSAGES.keys())}]")
        sys.exit(1)

    kind = sys.argv[1]
    asyncio.run(send(MESSAGES[kind]))
    print(f"已發送 {kind} 通知")


if __name__ == "__main__":
    main()
