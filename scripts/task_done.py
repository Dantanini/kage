#!/usr/bin/env python3
"""task_done.py — Notify Dante via Telegram when a branch task is complete.

Called by Claude Code after finishing work on a branch.

Usage:
  python3 scripts/task_done.py \\
    --branch feat/branch-guard \\
    --summary "pre-commit hook 擋 main/develop commit" \\
    --tests "test_blocks_main,test_blocks_develop,test_allows_feature" \\
    --prevents "在 main 上直接 commit"
"""

import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

# Load .env
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


def build_message(
    branch: str,
    summary: str,
    tests: list[str],
    prevents: str,
) -> str:
    """Format the notification message."""
    test_lines = "\n".join(f"  • {t}" for t in tests)
    return (
        f"✅ Branch 完成：{branch}\n\n"
        f"📝 {summary}\n\n"
        f"🧪 測試項目：\n{test_lines}\n\n"
        f"🛡️ 預防：{prevents}"
    )


def build_keyboard(branch: str) -> dict:
    """Build inline keyboard with Open PR and Ask buttons."""
    # Telegram callback_data limit: 64 bytes
    # Format: "task_pr:<branch>" / "task_ask:<branch>"
    pr_data = f"task_pr:{branch}"
    ask_data = f"task_ask:{branch}"

    # Truncate if needed (safety, shouldn't happen with normal branch names)
    if len(pr_data.encode("utf-8")) > 64:
        pr_data = pr_data[:64]
    if len(ask_data.encode("utf-8")) > 64:
        ask_data = ask_data[:64]

    return {
        "inline_keyboard": [[
            {"text": "🚀 開 PR", "callback_data": pr_data},
            {"text": "❓ 追問", "callback_data": ask_data},
        ]]
    }


def send_task_done(
    branch: str,
    summary: str,
    tests: list[str],
    prevents: str,
    token: str = "",
    chat_id: str = "",
) -> bool:
    """Send task completion notification with inline buttons."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_ADMIN_ID", "")

    if not token or not chat_id:
        logger.warning("Missing token or chat_id, skipping notification")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": int(chat_id),
        "text": build_message(branch, summary, tests, prevents),
        "reply_markup": build_keyboard(branch),
    }).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        logger.warning(f"Task done notification failed: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Send branch completion notification")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--tests", required=True, help="Comma-separated test names")
    parser.add_argument("--prevents", required=True)
    args = parser.parse_args()

    tests = [t.strip() for t in args.tests.split(",")]
    ok = send_task_done(args.branch, args.summary, tests, args.prevents)
    if ok:
        print(f"已發送完成通知：{args.branch}")
    else:
        print("發送失敗", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
