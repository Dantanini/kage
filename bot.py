"""TG Bot 薄殼 — 收訊息 → claude -p → 回傳結果。"""

import asyncio
import logging
import os
import shutil
from datetime import date
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

from router import route
from session import SessionManager

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Load .env file early (before any env var reads)
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _val = _line.split("=", 1)
            os.environ.setdefault(_key.strip(), _val.strip())

# Load config
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", "0"))
TIMEOUT_MINUTES = CONFIG["session"]["timeout_minutes"]

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
        cmd.extend(["--resume", session_id])
    else:
        cmd.extend(["--session-id", session_id])

    # Prepend date context on first message of session
    if not resume:
        prompt = f"[系統] 今天是 {date.today().isoformat()}。\n\n{prompt}"

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
    """Only allow admin. Silent ignore for others — don't reveal bot is alive."""
    user = update.effective_user
    if user.id != ADMIN_ID:
        logger.warning(f"Unauthorized: {user.id} ({user.full_name})")
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return
    await update.message.reply_text(
        "🤖 AI 助手已就緒\n\n"
        "直接打字就能對話（預設 Sonnet）\n\n"
        "切換模式：\n"
        "/course — 課程學習（Opus）\n"
        "/opus — 切換到 Opus（深度思考）\n"
        "/sonnet — 切回 Sonnet\n"
        "/done — 結束並儲存\n"
        "/restart — 重啟 Bot"
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


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return
    await update.message.reply_text("🔄 3 秒後重啟...")
    await asyncio.sleep(3)
    os._exit(0)


MORNING_PROMPT = """[系統] 今天是 {date}。這是早上摘要。

請執行以下步驟：
1. 讀 profile/current-focus.md 了解目前三條主線
2. 讀最近 3 天的 daily/*.md 了解近期進度
3. 讀 learning/INDEX.md 了解學習進度
4. 讀 decisions/INDEX.md 了解近期決策

然後給 Dante 一份簡短的今日建議：
- 今天最重要的 1-2 件事（根據主線優先順序）
- 學習可以從哪裡繼續
- 有沒有什麼卡住的需要處理"""

EVENING_PROMPT = """[系統] 今天是 {date}。這是晚上日結。

請執行以下步驟：
1. 讀今天的 daily/{date}.md（如果存在）
2. 讀 learning/INDEX.md 確認今天有沒有學習進度
3. 讀 inbox/raw-notes.md 看有沒有今天的零散想法

然後：
1. 更新或建立 daily/{date}.md，整理今天做了什麼
2. 更新 learning/INDEX.md（如果有變動）
3. 執行 python3 scripts/validate.py
4. 執行 python3 scripts/commit.py "日結: {date}"
5. 回報給 Dante 今天的摘要"""


async def cmd_morning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return
    status_msg = await update.message.reply_text("🌅 正在整理今日主線...")
    result = await _run_claude(
        MORNING_PROMPT.format(date=date.today().isoformat()),
        "sonnet", str(__import__('uuid').uuid4()), resume=False,
    )
    try:
        await status_msg.delete()
    except Exception:
        pass
    if len(result) <= 4000:
        await update.message.reply_text(result)
    else:
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i + 4000])


async def cmd_evening(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return
    status_msg = await update.message.reply_text("🌙 正在整理今日日結...")
    result = await _run_claude(
        EVENING_PROMPT.format(date=date.today().isoformat()),
        "sonnet", str(__import__('uuid').uuid4()), resume=False,
    )
    try:
        await status_msg.delete()
    except Exception:
        pass
    if len(result) <= 4000:
        await update.message.reply_text(result)
    else:
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i + 4000])


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return

    text = update.message.text
    if not text:
        return

    user_id = update.effective_user.id

    logger.info(f"Message: {text[:80]}...")
    model, intent = route(text)
    logger.info(f"Routed to model={model}, intent={intent}")

    # Strip command prefix before sending to Claude
    prompt = text
    if text.startswith("/"):
        parts = text.split(None, 1)
        prompt = parts[1] if len(parts) > 1 else ""

    # If command only (no prompt text), just switch model and confirm
    if not prompt:
        session = sessions.get_or_create(user_id, intent, model)
        session.model = model
        session.intent = intent
        await update.message.reply_text(f"已切換到 {model}")
        return

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

    # Only update model if user explicitly switched via command
    if text.startswith("/"):
        session.model = model
        session.intent = intent
    else:
        # Use session's current model (preserves /opus switch)
        model = session.model

    # Progress feedback — send status then keep typing indicator
    INTENT_LABEL = {
        "course": "📚 課程模式",
        "architecture": "🏗️ 架構思考",
        "decision": "⚖️ 決策分析",
        "note": "📝 筆記模式",
        "chat": "💬 對話",
    }
    status_msg = await update.message.reply_text(
        f"{INTENT_LABEL.get(intent, '💬')} | {model} | 思考中..."
    )

    # Keep sending typing action while Claude thinks
    async def keep_typing():
        try:
            while True:
                await update.message.chat.send_action("typing")
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass

    typing_task = asyncio.create_task(keep_typing())

    result = await _run_claude(prompt, model, session.session_id, resume=resume)

    typing_task.cancel()

    # Delete status message, send actual response
    try:
        await status_msg.delete()
    except Exception:
        pass
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
        BotCommand("course", "課程學習（Opus）"),
        BotCommand("opus", "切換 Opus"),
        BotCommand("sonnet", "切換 Sonnet"),
        BotCommand("morning", "今日主線摘要"),
        BotCommand("evening", "今日日結"),
        BotCommand("done", "結束對話並儲存"),
        BotCommand("restart", "重啟 Bot"),
    ]
    await app.bot.set_my_commands(commands)


def main():
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
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("morning", cmd_morning))
    app.add_handler(CommandHandler("evening", cmd_evening))
    app.add_handler(CommandHandler("course", handle_message))
    app.add_handler(CommandHandler("opus", handle_message))
    app.add_handler(CommandHandler("sonnet", handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
