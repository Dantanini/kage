"""tg_notify.py — Shared Telegram notification utilities.

Used by bot.py (memory save notifications) and auto_deploy.py.
Sends via raw Telegram Bot API (urllib), no dependency on python-telegram-bot.
"""

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)


def send_telegram_message(
    text: str,
    token: str = "",
    chat_id: str = "",
) -> bool:
    """Send a plain text message via Telegram Bot API.

    Returns True on success, False on failure. Never raises.
    """
    if not token or not chat_id:
        logger.warning("Missing token or chat_id, skipping notification")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": int(chat_id), "text": text}).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")
        return False


def build_memory_save_message(
    success: bool = True,
    qa_count: int = 0,
    error: str = "",
) -> str:
    """Build notification message for memory auto-save events."""
    if success:
        return f"✓ 記憶自動存檔完成（{qa_count} 則對話）"
    return f"✗ 記憶存檔失敗: {error}"
