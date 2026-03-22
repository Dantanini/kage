"""TG Bot 薄殼 — 收訊息 → claude -p → 回傳結果。"""

import asyncio
import logging
import os
import shutil
from pathlib import Path

import yaml
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from router import route, route_command, MODEL_MAP
from session import SessionManager

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", "0"))
TIMEOUT_MINUTES = CONFIG["session"]["timeout_minutes"]
MODEL_CONFIG = CONFIG.get("models", {})

# Override MODEL_MAP with config
for intent, model in MODEL_CONFIG.items():
    MODEL_MAP[intent] = model

# Session manager
sessions = SessionManager(timeout_minutes=TIMEOUT_MINUTES)


def _get_journal_path() -> str:
    path = os.environ.get("DEV_JOURNAL_PATH", "")
    if not path:
        path = str(Path.home() / "dev-journal")
    return path


def _find_claude() -> str:
    claude = shutil.which("claude")
    if claude:
        return claude
    candidates = [
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / ".claude" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise FileNotFoundError("claude CLI not found")


async def _run_claude(prompt: str, model: str, session_id: str, resume: bool = False) -> str:
    """Execute claude -p and return output."""
    claude_bin = _find_claude()
    journal_path = _get_journal_path()

    cmd = [claude_bin, "-p", "--model", model]
    if resume:
        cmd.extend(["--session-id", session_id, "--resume"])
    else:
        cmd.extend(["--session-id", session_id])
    cmd.append(prompt)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=journal_path,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip()
        logger.error(f"claude error: {err}")
        return f"⚠️ Claude 執行失敗:\n{err[:500]}"

    return stdout.decode().strip()


async def _check_auth(update: Update) -> bool:
    """Only allow admin for now."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ 未授權的使用者")
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return
    await update.message.reply_text(
        "🤖 AI 助手已就緒\n\n"
        "直接打字跟我對話，我會自動判斷意圖。\n"
        "或使用指令：/course /note /done"
    )


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return

    session = sessions.get(update.effective_user.id)
    if not session:
        await update.message.reply_text("目前沒有進行中的對話")
        return

    await update.message.reply_text("正在結束對話並儲存紀錄...")
    result = await _run_claude(
        "使用者要結束對話。請執行結束流程。",
        session.model,
        session.session_id,
        resume=True,
    )
    sessions.close(update.effective_user.id)
    await update.message.reply_text(result[:4000])
    await update.message.reply_text("✅ 對話已結束")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return

    text = update.message.text
    if not text:
        return

    user_id = update.effective_user.id

    # Route to model + intent
    model, intent = await route(text, MODEL_CONFIG)

    # Handle end intent with confirmation
    if intent == "end":
        session = sessions.get(user_id)
        if session:
            await update.message.reply_text(
                "要結束這次對話嗎？我會更新筆記和日誌。\n"
                "輸入 /done 確認，或繼續打字繼續對話。"
            )
            return
        else:
            await update.message.reply_text("目前沒有進行中的對話")
            return

    # Get or create session
    session = sessions.get_or_create(user_id, intent, model)
    resume = not session.is_first_message

    # Update model if intent changed (e.g., started chatting, now doing course)
    if intent in ("course", "architecture", "decision"):
        session.model = MODEL_CONFIG.get(intent, "opus")
        session.intent = intent
        model = session.model

    await update.message.chat.send_action("typing")

    result = await _run_claude(text, model, session.session_id, resume=resume)
    session.touch()

    # Split long messages (Telegram limit: 4096 chars)
    if len(result) <= 4000:
        await update.message.reply_text(result)
    else:
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i + 4000])


async def post_init(app: Application):
    """Set bot commands menu."""
    commands = [
        BotCommand("start", "啟動助手"),
        BotCommand("course", "進入課程學習模式"),
        BotCommand("note", "快速記筆記"),
        BotCommand("done", "結束對話並儲存"),
    ]
    await app.bot.set_my_commands(commands)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        # Try .env file
        env_path = Path(__file__).resolve().parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()
            token = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        raise SystemExit(1)

    journal_path = _get_journal_path()
    if not Path(journal_path).exists():
        logger.error(f"DEV_JOURNAL_PATH not found: {journal_path}")
        raise SystemExit(1)

    logger.info(f"Bot starting, journal: {journal_path}")

    app = Application.builder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
