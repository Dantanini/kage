"""TG Bot 薄殼 — 收訊息 → claude -p → 回傳結果。"""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import date
from pathlib import Path

import yaml
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from memory import MemoryStore
from plan_v2 import PlanStore, PlanStatus
from prompt_specs import PLAN_SPECS, build_prompt
from router import route
from session import SessionManager
from tg_notify import build_memory_save_message, send_telegram_message
from workflows import (
    build_morning_steps,
    build_evening_steps,
    run_workflow,
    format_workflow_results,
)

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
REPO_DIR = Path(__file__).resolve().parent
LAST_ACTIVITY_FILE = REPO_DIR / ".last_activity"


def _touch_activity():
    """Write current timestamp for auto-deploy idle check."""
    LAST_ACTIVITY_FILE.write_text(str(time.time()))
TIMEOUT_MINUTES = CONFIG["session"]["timeout_minutes"]

# Repo management — which directory claude -p runs in
REPOS = {
    "journal": str(Path(os.environ.get("DEV_JOURNAL_PATH", "")) or Path.home() / "dev-journal"),
    "kage": str(Path.home() / "kage"),
    "home": str(Path.home()),
}
_current_repo: dict[str, str] = {"name": "journal", "path": REPOS["journal"]}

# Session manager
sessions = SessionManager(timeout_minutes=TIMEOUT_MINUTES)

# Persistent memory
memory_store = MemoryStore(base_dir=REPOS["journal"])
plan_store = PlanStore(local_dir=str(REPO_DIR / ".local"))

# Track pending plan record state (chat_id → True when waiting for next message)
_pending_plan_record: dict[int, bool] = {}
# Track pending plan adjust state (chat_id → True when waiting for adjust feedback)
_pending_plan_adjust: dict[int, bool] = {}
# Track pending plan ask state (chat_id → branch name for follow-up PR button)
_pending_plan_ask_branch: dict[int, str] = {}
# Marker prefix in task_ask prompt messages, used to extract branch from reply_to_message
TASK_ASK_MARKER = "❓ 針對"


# --- Session hooks ---
def _make_git_pull_hook():
    """Factory: creates a start hook that git-pulls the current repo."""
    async def hook(session):
        repo_path = _current_repo.get("path", _get_journal_path())
        err = await _git_pull(repo_path)
        if err:
            logger.warning(f"SessionStart git pull failed: {err}")
    return hook


def _make_memory_save_hook():
    """Factory: creates an end hook that saves session memory."""
    async def hook(session):
        if not session.qa_log:
            return
        prompt = memory_store.build_save_prompt(session.qa_log)
        if not prompt:
            return
        import uuid as _uuid
        result = await _run_claude(
            prompt, "sonnet", str(_uuid.uuid4()), resume=False,
        )
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        admin_id = os.environ.get("TELEGRAM_ADMIN_ID", "")
        if result.startswith("\u26a0\ufe0f"):
            logger.warning(f"Memory save failed: {result[:200]}")
            msg = build_memory_save_message(success=False, error=result[:100])
        else:
            logger.info("Session memory saved successfully")
            msg = build_memory_save_message(success=True, qa_count=len(session.qa_log))
        send_telegram_message(msg, token=token, chat_id=admin_id)
    return hook


sessions.register_start_hook(_make_git_pull_hook)
sessions.register_end_hook(_make_memory_save_hook)


def _get_journal_path() -> str:
    return REPOS["journal"]


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


MAX_RETRIES = 2
QA_LOG_FLUSH_SIZE = 20_000  # chars


async def _git_pull(repo_path: str) -> str | None:
    """Run git pull in the given repo. Returns error message or None on success."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "pull", "--ff-only",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = (stdout.decode() + stderr.decode()).strip()
        if proc.returncode != 0:
            logger.warning(f"git pull failed in {repo_path}: {output}")
            return f"git pull 失敗: {output[:200]}"
        logger.info(f"git pull in {repo_path}: {output}")
        return None
    except Exception as e:
        logger.warning(f"git pull error: {e}")
        return str(e)


async def _kill_stale_claude() -> None:
    """Kill any stopped/zombie claude -p processes to prevent session conflicts."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pgrep", "-f", "claude.*-p",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if not stdout.strip():
            return
        for pid_str in stdout.decode().strip().split("\n"):
            pid = int(pid_str)
            # Check process state — kill stopped (T) or zombie (Z) ones
            try:
                stat = Path(f"/proc/{pid}/stat").read_text()
                state = stat.split(")")[1].strip().split()[0]
                if state in ("T", "t", "Z"):
                    os.kill(pid, 9)
                    logger.info(f"Killed stale claude process {pid} (state={state})")
            except (FileNotFoundError, ProcessLookupError, IndexError):
                pass
    except Exception as e:
        logger.debug(f"_kill_stale_claude: {e}")


async def _run_claude_once(prompt: str, model: str, session_id: str, resume: bool = False, cwd: str | None = None, inject_plan: bool = False) -> str:
    """Single attempt to execute claude -p and return output."""
    claude_bin = _find_claude()
    work_dir = cwd or _current_repo.get("path", _get_journal_path())

    # NOTE: --dangerously-skip-permissions is required because in subprocess mode,
    # Claude CLI's permission prompts get mixed into stdout as plain text.
    # Compensating controls: single-admin auth (bot.py:_check_auth),
    # CLAUDE.md operation rules, and cwd locked to predefined repos only.
    # GitHub branch protection is enabled on all remote branches.
    # TODO: migrate to --permission-mode allowedTools when CLI supports clean stdout.
    cmd = [claude_bin, "-p", "--model", model, "--dangerously-skip-permissions"]
    if resume:
        cmd.extend(["--resume", session_id])
    else:
        cmd.extend(["--session-id", session_id])

    if not resume:
        recovery_notice = memory_store.check_recovery_needed(REPO_DIR / ".needs_recovery")
        memory_prefix = memory_store.build_context_prefix()
        # Only inject plan context for interactive chat sessions; skip for
        # workflows, course, note, task execution, and background tasks.
        plan_prefix = plan_store.build_context_injection() if inject_plan else ""
        prompt = f"[系統] 今天是 {date.today().isoformat()}。工作目錄：{work_dir}\n{recovery_notice}{memory_prefix}{plan_prefix}\n{prompt}"

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=work_dir,
    )
    stdout, stderr = await proc.communicate(input=prompt.encode())

    if proc.returncode != 0:
        raise RuntimeError(stderr.decode().strip())

    return stdout.decode().strip()


async def _run_claude(prompt: str, model: str, session_id: str, resume: bool = False, cwd: str | None = None, inject_plan: bool = False) -> str:
    """Execute claude -p with retry (max MAX_RETRIES). Returns error string on final failure."""
    last_err = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await _run_claude_once(prompt, model, session_id, resume=resume, cwd=cwd, inject_plan=inject_plan)
        except Exception as e:
            last_err = str(e)
            logger.warning(f"claude attempt {attempt + 1} failed: {last_err[:200]}")
            # Session conflict → clean up stale processes, start fresh
            if "already in use" in last_err:
                logger.info("Session conflict detected, cleaning up and falling back to new session")
                await _kill_stale_claude()
                session_id = str(__import__("uuid").uuid4())
                resume = False
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2)

    logger.error(f"claude failed after {MAX_RETRIES + 1} attempts: {last_err}")
    return f"⚠️ Claude 執行失敗（已重試 {MAX_RETRIES} 次）:\n{last_err[:400]}"


async def _flush_qa_log(session, cwd: str | None = None) -> str | None:
    """Send accumulated QA log to a fresh Claude session to write course notes."""
    if not session.qa_log:
        return None

    import uuid as _uuid
    log_text = "\n\n---\n\n".join(
        f"**問：** {q}\n\n**答：** {a}" for q, a in session.qa_log
    )
    prompt = (
        "以下是這次學習對話的完整問答紀錄。請整理成結構化課程筆記，"
        "存到 learning/ 對應的檔案，並更新 learning/INDEX.md。\n\n" + log_text
    )
    result = await _run_claude(prompt, session.model, str(_uuid.uuid4()), resume=False, cwd=cwd)
    session.qa_log.clear()
    return result


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
        "🤖 AI 助手已就緒（直接打字就能對話）\n\n"
        "📋 日常：\n"
        "/morning — 今天該做什麼\n"
        "/evening — 日結存檔（記憶+daily+README）\n"
        "/done — 結束對話並儲存\n\n"
        "📚 學習：\n"
        "/course — 開始學習（Opus）\n\n"
        "⚙️ 切換：\n"
        "/opus — 整段切 Opus  /sonnet — 切回\n"
        "/repo — 切工作目錄  /restart — 重啟"
    )


async def cmd_deep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch current session to Opus without losing conversation context."""
    if not await _check_auth(update):
        return

    _touch_activity()
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()

    # Get or create session
    session = sessions.get(user_id)
    if not session:
        session = sessions.create(user_id, "chat", "opus")
    else:
        session.model = "opus"

    # Extract text after /deep
    parts = text.split(None, 1)
    prompt = parts[1] if len(parts) > 1 else ""

    if not prompt:
        await update.message.reply_text("已切換至 Opus，對話繼續。")
        return

    # Has text — switch model and send to Claude immediately
    resume = not session.is_first_message

    hook_errors = await session.run_start_hooks()
    for err in hook_errors:
        logger.warning(f"Session start hook: {err}")

    status_msg = await update.message.reply_text("🧠 | opus | 思考中...")

    async def keep_typing():
        try:
            while True:
                await update.message.chat.send_action("typing")
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass

    typing_task = asyncio.create_task(keep_typing())
    result = await _run_claude(prompt, "opus", session.session_id, resume=resume, inject_plan=True)
    typing_task.cancel()

    try:
        await status_msg.delete()
    except Exception:
        pass

    if not result.startswith("⚠️"):
        session.touch()
        session.qa_log.append((prompt, result))

    if len(result) <= 4000:
        await update.message.reply_text(result)
    else:
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i + 4000])


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return

    session = sessions.get(update.effective_user.id)
    if not session:
        await update.message.reply_text("目前沒有進行中的對話")
        return

    await update.message.reply_text("正在結束對話並儲存紀錄...")

    # Flush QA log first (backup of full conversation for notes)
    if session.qa_log:
        flush_result = await _flush_qa_log(session)
        if flush_result and flush_result.startswith("⚠️"):
            logger.warning(f"QA log flush failed: {flush_result[:200]}")

    result = await _run_claude(
        "使用者要結束對話。請執行結束流程。",
        session.model,
        session.session_id,
        resume=True,
    )
    await sessions.close(update.effective_user.id)
    await update.message.reply_text(result[:4000])
    await update.message.reply_text("✅ 對話已結束")


async def cmd_repo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return
    args = update.message.text.split(None, 1)
    if len(args) < 2:
        lines = [f"目前：{_current_repo['name']} ({_current_repo['path']})\n", "可用 repo："]
        for name, path in REPOS.items():
            exists = "✅" if Path(path).exists() else "❌"
            lines.append(f"  {exists} /repo {name} → {path}")
        await update.message.reply_text("\n".join(lines))
        return

    name = args[1].strip().lower()
    if name not in REPOS:
        await update.message.reply_text(f"未知 repo: {name}\n可用: {', '.join(REPOS.keys())}")
        return

    _current_repo["name"] = name
    _current_repo["path"] = REPOS[name]
    # Close current session since we're switching context
    await sessions.close(update.effective_user.id)
    await update.message.reply_text(f"已切換到 {name} ({REPOS[name]})\nSession 已重置")


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return

    # Save all active sessions before restart
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if session and session.qa_log:
        await update.message.reply_text("💾 先儲存記憶再重啟...")
        await sessions.close(user_id)

    # Pull both repos before restart
    await update.message.reply_text("📥 正在拉取最新程式碼...")
    pull_errors = []
    # Ensure kage is on main before pulling
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "checkout", "main",
            cwd=str(REPO_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    except Exception as e:
        logger.warning(f"git checkout main failed: {e}")
    for name, path in [("kage", str(REPO_DIR)), ("journal", REPOS["journal"])]:
        err = await _git_pull(path)
        if err:
            pull_errors.append(f"{name}: {err}")

    if pull_errors:
        await update.message.reply_text(
            "⚠️ Git pull 失敗（重啟仍會繼續）：\n" + "\n".join(pull_errors)
        )

    await update.message.reply_text("🔄 3 秒後重啟...")
    await asyncio.sleep(3)
    # Write notify file so post_init can confirm restart to user
    (REPO_DIR / ".restart_notify").write_text(str(update.effective_chat.id))
    # Clean exit — remove recovery marker
    (REPO_DIR / ".needs_recovery").unlink(missing_ok=True)
    os._exit(0)


def _plan_buttons_for_status(status: PlanStatus, has_draft: bool = False) -> InlineKeyboardMarkup:
    """Generate buttons based on current plan status."""
    if status == PlanStatus.EMPTY:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 撰寫", callback_data="plan_write")],
        ])
    elif status == PlanStatus.DRAFT:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📝 撰寫", callback_data="plan_write"),
                InlineKeyboardButton("🧠 規劃", callback_data="plan_analyze"),
            ],
        ])
    elif status == PlanStatus.PLANNED:
        buttons = [
            InlineKeyboardButton("📝 撰寫", callback_data="plan_write"),
        ]
        if has_draft:
            buttons.append(InlineKeyboardButton("🧠 規劃", callback_data="plan_analyze"))
        buttons.append(InlineKeyboardButton("🔧 調整", callback_data="plan_adjust"))
        buttons.append(InlineKeyboardButton("🔨 執行", callback_data="plan_execute"))
        return InlineKeyboardMarkup([buttons])
    elif status == PlanStatus.EXECUTING:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("⏸️ 暫停", callback_data="plan_pause")],
        ])
    return InlineKeyboardMarkup([])


def _plan_status_text(status: PlanStatus) -> str:
    """Status emoji + text."""
    return {
        PlanStatus.EMPTY: "📭 目前無計畫",
        PlanStatus.DRAFT: "📝 草稿中",
        PlanStatus.PLANNED: "📋 已規劃，待執行",
        PlanStatus.EXECUTING: "🔨 執行中",
    }.get(status, "")


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Plan menu. /plan = show status + buttons, /plan <text> = quick append."""
    if not await _check_auth(update):
        return

    text = (update.message.text or "").strip()
    args = text.split(None, 1)
    body = args[1] if len(args) > 1 else ""

    if body:
        # /plan delete [N]
        if body.lower().startswith("delete"):
            parts = body.split(None, 1)
            if len(parts) < 2:
                # Show numbered list so user knows what index to use
                items = plan_store.all_items_numbered()
                if not items:
                    await update.message.reply_text("📭 目前沒有項目可刪除。")
                else:
                    lines = [f"{idx}. {line}" for (_, line, idx) in items]
                    await update.message.reply_text(
                        "請輸入要刪除的項目編號，例如 `/plan delete 2`\n\n"
                        + "\n".join(lines),
                        parse_mode="Markdown",
                    )
                return

            raw_n = parts[1].strip()
            if not raw_n.isdigit():
                await update.message.reply_text(
                    f"❌ 請輸入數字，例如 `/plan delete 2`（收到：`{raw_n}`）",
                    parse_mode="Markdown",
                )
                return

            n = int(raw_n)
            deleted = plan_store.delete_item(n)
            if deleted is None:
                await update.message.reply_text(f"❌ 找不到項目 #{n}，請先用 `/plan delete` 查看編號。", parse_mode="Markdown")
                return

            status = plan_store.status
            content = plan_store.read()
            preview = content[:2000] if content else ""
            keyboard = _plan_buttons_for_status(status, has_draft=bool(plan_store.draft_items()))
            msg = f"🗑️ 已刪除 #{n}：`{deleted}`"
            if preview:
                msg += f"\n\n{preview}"
            await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
            return

        # Quick append: /plan <text>
        plan_store.append(body)
        status = plan_store.status
        content = plan_store.read()
        preview = content[:2000] if len(content) > 2000 else content
        keyboard = _plan_buttons_for_status(status, has_draft=bool(plan_store.draft_items()))
        await update.message.reply_text(
            f"✅ 已記錄\n\n{preview}",
            reply_markup=keyboard,
        )
        return

    # No text → show current plan + buttons
    status = plan_store.status
    status_text = _plan_status_text(status)
    content = plan_store.read()
    preview = content[:2000] if content else ""
    keyboard = _plan_buttons_for_status(status, has_draft=bool(plan_store.draft_items()))

    if preview:
        await update.message.reply_text(
            f"{status_text}\n\n{preview}",
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            f"{status_text}\n\n選擇操作：",
            reply_markup=keyboard,
        )


async def handle_release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dispatch /release and /release confirm."""
    if not await _check_auth(update):
        return
    text = (update.message.text or "").strip()
    if "confirm" in text.lower():
        await cmd_release_confirm(update, context)
    else:
        await cmd_release(update, context)


async def cmd_release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run release.py --dry-run and show result. No LLM token cost."""
    _touch_activity()
    await update.message.reply_text("🚀 正在檢查 develop → main 差異...")

    try:
        result = subprocess.run(
            ["python3", str(REPO_DIR / "release.py"), "--dry-run"],
            capture_output=True, text=True, timeout=30, cwd=REPO_DIR,
        )
        output = result.stdout.strip() or result.stderr.strip() or "No output"

        if "No commits" in output:
            await update.message.reply_text("沒有新的 commits，不需要 release。")
            return

        # Show preview with inline confirm/cancel buttons
        preview = output[:3000]
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ 確認開 PR", callback_data="release_confirm"),
            InlineKeyboardButton("❌ 取消", callback_data="release_cancel"),
        ]])
        await update.message.reply_text(
            f"📋 Release 預覽：\n\n{preview}\n\n"
            f"確認要開 PR 嗎？",
            reply_markup=keyboard,
        )
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⚠️ release.py 執行逾時")
    except Exception as e:
        await update.message.reply_text(f"⚠️ 執行失敗: {e}")


async def cmd_release_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Actually create the release PR."""
    _touch_activity()
    await update.message.reply_text("🚀 正在建立 PR...")

    try:
        result = subprocess.run(
            ["python3", str(REPO_DIR / "release.py")],
            capture_output=True, text=True, timeout=30, cwd=REPO_DIR,
        )
        output = result.stdout.strip() or result.stderr.strip()
        if result.returncode == 0:
            await update.message.reply_text(f"✓ PR 已建立！\n{output}")
        else:
            await update.message.reply_text(f"⚠️ 失敗:\n{output}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ 執行失敗: {e}")


async def cmd_morning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return
    status_msg = await update.message.reply_text("🌅 正在整理今日主線（分步執行中）...")
    pull_err = await _git_pull(_get_journal_path())
    if pull_err:
        await update.message.reply_text(f"⚠️ {pull_err}\n繼續執行...")

    steps = build_morning_steps()
    results = await run_workflow(steps, _run_claude, cwd=_get_journal_path())
    result = format_workflow_results(results)

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
    status_msg = await update.message.reply_text("🌙 正在整理今日日結（分步執行中）...")
    pull_err = await _git_pull(_get_journal_path())
    if pull_err:
        await update.message.reply_text(f"⚠️ {pull_err}\n繼續執行...")

    steps = build_evening_steps()
    results = await run_workflow(steps, _run_claude, cwd=_get_journal_path())
    result = format_workflow_results(results)

    try:
        await status_msg.delete()
    except Exception:
        pass
    if len(result) <= 4000:
        await update.message.reply_text(result)
    else:
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i + 4000])


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks from notifications."""
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    _touch_activity()

    action = query.data
    chat_id = query.message.chat_id

    # Sync repo before morning/evening tasks
    if action in ("morning", "evening"):
        pull_err = await _git_pull(_get_journal_path())
        if pull_err:
            await context.bot.send_message(chat_id, f"⚠️ {pull_err}\n繼續執行...")

    if action == "release_confirm":
        await query.edit_message_text("🚀 正在建立 PR...")
        try:
            res = subprocess.run(
                ["python3", str(REPO_DIR / "release.py")],
                capture_output=True, text=True, timeout=30, cwd=REPO_DIR,
            )
            output = res.stdout.strip() or res.stderr.strip()
            if res.returncode == 0:
                await query.edit_message_text(f"✓ PR 已建立！\n{output}")
            else:
                await query.edit_message_text(f"⚠️ 失敗:\n{output}")
        except Exception as e:
            await query.edit_message_text(f"⚠️ 執行失敗: {e}")
        return

    if action == "release_cancel":
        await query.edit_message_text("❌ Release 已取消。")
        return

    if action == "morning":
        status_msg = await context.bot.send_message(chat_id, "🌅 正在整理今日主線（分步執行中）...")
        steps = build_morning_steps()
        results = await run_workflow(steps, _run_claude, cwd=_get_journal_path())
        result = format_workflow_results(results)
    elif action == "evening":
        status_msg = await context.bot.send_message(chat_id, "🌙 正在整理今日日結（分步執行中）...")
        steps = build_evening_steps()
        results = await run_workflow(steps, _run_claude, cwd=_get_journal_path())
        result = format_workflow_results(results)
    # ── Plan v2 actions ──
    elif action == "plan_write":
        await query.edit_message_text("📝 請輸入計畫內容（下一則訊息會被記錄）：")
        _pending_plan_record[chat_id] = True
        return
    elif action == "plan_analyze":
        draft = plan_store.read_draft()
        if not draft:
            await query.edit_message_text("📭 沒有草稿可分析。先撰寫內容。")
            return
        await query.edit_message_text("🧠 Opus 正在分析計畫...")
        spec = PLAN_SPECS["plan_analyze"]
        planned = plan_store.read_planned()
        planned_context = f"【已規劃的項目（不要動，不要重複）】\n{planned}\n\n" if planned else ""
        prompt = build_prompt(spec, {"draft": draft, "planned_context": planned_context})
        import uuid as _uuid
        result = await _run_claude(prompt, spec.model, str(_uuid.uuid4()), resume=False)
        if not result.startswith("⚠️") and spec.validate_output(result):
            plan_store.set_planned(result)
            user_id = query.from_user.id
            sess = sessions.get_or_create(user_id, "plan", "opus")
            sess.model = "opus"
            preview = result[:3000]
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔧 調整", callback_data="plan_adjust"),
                    InlineKeyboardButton("🔨 執行", callback_data="plan_execute"),
                ],
            ])
            await context.bot.send_message(chat_id, f"📋 規劃結果：\n\n{preview}", reply_markup=keyboard)
        elif result.startswith("⚠️"):
            await context.bot.send_message(chat_id, f"⚠️ 分析失敗：{result[:500]}")
        else:
            await context.bot.send_message(chat_id, "⚠️ Opus 回覆格式不正確（沒有 checklist），請重試或調整草稿。")
        return
    elif action == "plan_adjust":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id, "🔧 請回覆你想調整的內容（下一則訊息）：")
        _pending_plan_adjust[chat_id] = True
        return
    elif action == "plan_execute":
        if plan_store.status != PlanStatus.PLANNED:
            await query.edit_message_text("📭 沒有計畫可執行。")
            return
        plan_store.set_executing()
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id, "🔨 開始逐項執行...")
        await _run_next_plan_item(chat_id, context)
        return
    elif action.startswith("plan_pr:"):
        branch = action[len("plan_pr:"):]
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id, f"🚀 正在為 {branch} 開 PR...")
        pr_script = str(REPO_DIR / "scripts" / "pr.sh")
        proc = await asyncio.create_subprocess_exec(
            "bash", pr_script, "--branch", branch,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(REPO_DIR),
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode().strip() or stderr.decode().strip()
        if proc.returncode == 0:
            await context.bot.send_message(chat_id, f"✅ PR 已開：\n{output}")
            # PR success → auto run next item
            if plan_store.pending_items():
                await _run_next_plan_item(chat_id, context)
            elif plan_store.all_completed():
                await context.bot.send_message(chat_id, "🎉 所有項目完成。")
        else:
            await context.bot.send_message(chat_id, f"❌ 開 PR 失敗：\n{output}")
        return
    elif action.startswith("plan_ask:"):
        branch = action[len("plan_ask:"):]
        await query.edit_message_reply_markup(reply_markup=None)
        # Store branch so we can show PR button after answer
        _pending_plan_ask_branch[chat_id] = branch
        await context.bot.send_message(chat_id, f"❓ 針對 {branch} 提問，請輸入你的問題：")
        return
    elif action == "plan_pause":
        plan_store.pause()
        content = plan_store.read()
        preview = content[:2000] if content else ""
        keyboard = _plan_buttons_for_status(plan_store.status, has_draft=bool(plan_store.draft_items()))
        await query.edit_message_text(
            f"⏸️ 已暫停\n\n{preview}",
            reply_markup=keyboard,
        )
        return
    elif action.startswith("task_pr:"):
        branch = action[len("task_pr:"):]
        await query.edit_message_text(f"🚀 正在為 {branch} 開 PR...")
        pr_script = str(REPO_DIR / "scripts" / "pr.sh")
        proc = await asyncio.create_subprocess_exec(
            "bash", pr_script, "--branch", branch,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(REPO_DIR),
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode().strip() or stderr.decode().strip()
        if proc.returncode == 0:
            await context.bot.send_message(chat_id, f"✅ PR 已開：\n{output}")
        else:
            await context.bot.send_message(chat_id, f"❌ 開 PR 失敗：\n{output}")
        return
    elif action.startswith("task_ask:"):
        branch = action[len("task_ask:"):]
        await query.edit_message_text(
            f"{TASK_ASK_MARKER} {branch} 提問\n\n"
            f"請「回覆」這則訊息輸入你的問題："
        )
        return
    else:
        return

    try:
        await status_msg.delete()
    except Exception:
        pass

    if len(result) <= 4000:
        await context.bot.send_message(chat_id, result)
    else:
        for i in range(0, len(result), 4000):
            await context.bot.send_message(chat_id, result[i:i + 4000])



def is_supported_document(filename: str | None) -> bool:
    """Check if a document file type is supported (PDF only for now)."""
    if not filename:
        return False
    return filename.lower().endswith(".pdf")


def build_document_prompt(file_path: str, filename: str, caption: str | None) -> str:
    """Build a prompt that instructs Claude to read and respond to a document."""
    effective_caption = caption if caption else f"請閱讀並摘要這份文件：{filename}"
    return (
        f"使用者傳了一份文件 {filename}，存在 {file_path}。"
        f"請先用 Read tool 讀取這份文件，然後回應使用者的要求：{effective_caption}"
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document messages — download PDF, build prompt, pass to Claude."""
    if not await _check_auth(update):
        return

    filename = update.message.document.file_name
    if not is_supported_document(filename):
        await update.message.reply_text("⚠️ 目前只支援 PDF 文件")
        return

    _touch_activity()
    user_id = update.effective_user.id
    caption = update.message.caption or ""

    # Download to temp file preserving extension
    file = await context.bot.get_file(update.message.document.file_id)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir="/tmp") as tmp:
        await file.download_to_drive(tmp.name)
        doc_path = tmp.name

    prompt = build_document_prompt(doc_path, filename, caption)

    model = "sonnet"
    intent = "chat"
    session = sessions.get_or_create(user_id, intent, model)
    resume = not session.is_first_message

    if not session.is_first_message:
        model = session.model

    hook_errors = await session.run_start_hooks()
    for err in hook_errors:
        logger.warning(f"Session start hook: {err}")

    status_msg = await update.message.reply_text(
        f"📄 文件分析中 | {model} | 思考中..."
    )

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

    try:
        await status_msg.delete()
    except Exception:
        pass

    # Clean up temp file
    try:
        os.unlink(doc_path)
    except OSError:
        pass

    if not result.startswith("⚠️"):
        session.touch()
        session.qa_log.append((f"[文件] {filename}: {caption or '請摘要'}", result))

    if len(result) <= 4000:
        await update.message.reply_text(result)
    else:
        for i in range(0, len(result), 4000):
            await context.bot.send_message(update.effective_chat.id, result[i:i + 4000])


def build_photo_prompt(image_path: str, caption: str | None) -> str:
    """Build a prompt that instructs Claude to read and respond to a photo."""
    effective_caption = caption if caption else "請描述這張圖片"
    return (
        f"使用者傳了一張圖片，存在 {image_path}。"
        f"請先用 Read tool 讀取這張圖片，然後回應使用者的要求：{effective_caption}"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages — download, build prompt, pass to Claude."""
    if not await _check_auth(update):
        return

    _touch_activity()
    user_id = update.effective_user.id

    # Get the largest photo (last in the array)
    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    # Download to temp file
    file = await context.bot.get_file(photo.file_id)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, dir="/tmp") as tmp:
        await file.download_to_drive(tmp.name)
        image_path = tmp.name

    prompt = build_photo_prompt(image_path, caption)

    # Use existing session logic
    model = "sonnet"
    intent = "chat"
    session = sessions.get_or_create(user_id, intent, model)
    resume = not session.is_first_message

    # Use session's current model if already in a session
    if not session.is_first_message:
        model = session.model

    hook_errors = await session.run_start_hooks()
    for err in hook_errors:
        logger.warning(f"Session start hook: {err}")

    status_msg = await update.message.reply_text(
        f"🖼️ 圖片分析中 | {model} | 思考中..."
    )

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

    try:
        await status_msg.delete()
    except Exception:
        pass

    # Clean up temp file
    try:
        os.unlink(image_path)
    except OSError:
        pass

    if not result.startswith("⚠️"):
        session.touch()
        session.qa_log.append((f"[圖片] {caption or '請描述這張圖片'}", result))

    if len(result) <= 4000:
        await update.message.reply_text(result)
    else:
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i + 4000])


async def _run_next_plan_item(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute ONE plan item, then stop and wait for user action.

    Flow: execute → detect branch → record → send result with buttons → STOP.
    Next item only runs when user presses 開PR and PR succeeds.
    """
    items = plan_store.parse_planned_items()
    total = len(items) + len(plan_store.read_completed().split("\n"))  # rough total
    pending = plan_store.pending_items()
    if not pending:
        if plan_store.all_completed():
            await context.bot.send_message(chat_id, "🎉 所有項目完成。")
        else:
            await context.bot.send_message(chat_id, "📭 沒有待執行項目。")
        return

    # Execute first pending item
    item = pending[0]
    parsed = plan_store.parse_planned_items()
    task_info = parsed[0] if parsed else {"task": item.replace("- [ ]", "").strip(), "branch": None, "repo": None}
    task_desc = task_info["task"]
    planned_branch = task_info.get("branch") or ""

    current = len(pending)
    idx = total - current + 1
    await context.bot.send_message(chat_id, f"▶️ [{idx}] 正在執行：{task_desc[:100]}")

    import uuid as _uuid
    spec = PLAN_SPECS["plan_execute"]
    prompt = build_prompt(spec, {"task": task_desc})
    result = await _run_claude(prompt, spec.model, str(_uuid.uuid4()), resume=False)

    if not result.startswith("⚠️"):
        # Detect branch: use planned branch or try git branch --show-current
        branch = planned_branch or "unknown"
        plan_store.complete_item(task_desc[:30], branch=branch)

        preview = result[:3000]
        # Encode branch in callback_data for PR button
        branch_safe = branch[:40]  # TG callback_data limit is 64 bytes
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 開 PR", callback_data=f"plan_pr:{branch_safe}"),
                InlineKeyboardButton("❓ 追問", callback_data=f"plan_ask:{branch_safe}"),
            ],
            [
                InlineKeyboardButton("⏸️ 暫停", callback_data="plan_pause"),
            ],
        ])
        await context.bot.send_message(
            chat_id,
            f"✅ [{idx}] 完成：{task_desc[:50]}\n\n{preview}",
            reply_markup=keyboard,
        )
        # ← STOP HERE. Don't run next item. Wait for button press.
    else:
        await context.bot.send_message(chat_id, f"⚠️ [{idx}] 失敗：{result[:500]}")


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward unregistered /commands to handle_message instead of silently dropping."""
    await handle_message(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update):
        return

    _touch_activity()

    text = update.message.text
    if not text:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Intercept pending plan record — pure append, no LLM
    if _pending_plan_record.pop(chat_id, False):
        plan_store.append(text)
        status = plan_store.status
        content = plan_store.read()
        preview = content[:2000] if len(content) > 2000 else content
        keyboard = _plan_buttons_for_status(status, has_draft=bool(plan_store.draft_items()))
        await update.message.reply_text(
            f"✅ 已記錄\n\n{preview}",
            reply_markup=keyboard,
        )
        return

    # Intercept pending plan adjust — send to Opus for re-planning
    if _pending_plan_adjust.pop(chat_id, False):
        spec = PLAN_SPECS["plan_adjust"]
        current_plan = plan_store.read_planned()
        prompt = build_prompt(spec, {"current_plan": current_plan, "user_feedback": text})
        await update.message.reply_text("🧠 Opus 正在調整計畫...")
        import uuid as _uuid
        result = await _run_claude(prompt, spec.model, str(_uuid.uuid4()), resume=False)
        if not result.startswith("⚠️") and spec.validate_output(result):
            plan_store.set_planned(result)
            preview = result[:3000]
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔧 調整", callback_data="plan_adjust"),
                    InlineKeyboardButton("🔨 執行", callback_data="plan_execute"),
                ],
            ])
            await update.message.reply_text(f"📋 調整後的計畫：\n\n{preview}", reply_markup=keyboard)
        elif result.startswith("⚠️"):
            await update.message.reply_text(f"⚠️ 調整失敗：{result[:500]}")
        else:
            await update.message.reply_text("⚠️ Opus 回覆格式不正確（沒有 checklist），請重試。")
        return

    # Intercept pending plan ask — answer question then show PR/ask buttons
    branch = _pending_plan_ask_branch.pop(chat_id, None)
    if branch:
        import uuid as _uuid
        result = await _run_claude(text, "sonnet", str(_uuid.uuid4()), resume=False)
        preview = result[:3000] if not result.startswith("⚠️") else result[:500]
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 開 PR", callback_data=f"plan_pr:{branch}"),
                InlineKeyboardButton("❓ 追問", callback_data=f"plan_ask:{branch}"),
            ],
            [
                InlineKeyboardButton("⏸️ 暫停", callback_data="plan_pause"),
            ],
        ])
        await update.message.reply_text(preview, reply_markup=keyboard)
        return

    # Intercept reply to task_ask prompt — extract branch from replied message
    reply_msg = update.message.reply_to_message
    if reply_msg and reply_msg.text and reply_msg.text.startswith(TASK_ASK_MARKER):
        # Extract branch from "❓ 針對 <branch> 提問"
        marker_line = reply_msg.text.split("\n")[0]
        branch = marker_line.replace(TASK_ASK_MARKER, "").replace("提問", "").strip()

        import uuid as _uuid
        prompt = (
            f"使用者針對 branch `{branch}` 提問。"
            f"請先用 `git log --oneline {branch}` 和 `git diff develop..{branch}` "
            f"了解這個 branch 的改動，再回答以下問題：\n\n{text}"
        )
        status_msg = await update.message.reply_text(f"🔍 查看 {branch} 中...")

        async def keep_typing():
            try:
                while True:
                    await update.message.chat.send_action("typing")
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                pass

        typing_task = asyncio.create_task(keep_typing())
        result = await _run_claude(prompt, "sonnet", str(_uuid.uuid4()), resume=False)
        typing_task.cancel()

        try:
            await status_msg.delete()
        except Exception:
            pass

        # Send answer
        if len(result) <= 4000:
            await update.message.reply_text(result)
        else:
            for i in range(0, len(result), 4000):
                await update.message.reply_text(result[i:i + 4000])

        # Re-show buttons (uses top-level import)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 開 PR", callback_data=f"task_pr:{branch}"),
            InlineKeyboardButton("❓ 追問", callback_data=f"task_ask:{branch}"),
        ]])
        await update.message.reply_text(
            f"還有其他問題嗎？（branch: {branch}）",
            reply_markup=keyboard,
        )
        return

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

    # Run start hooks on first message (git pull, etc.)
    hook_errors = await session.run_start_hooks()
    for err in hook_errors:
        logger.warning(f"Session start hook: {err}")

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

    result = await _run_claude(prompt, model, session.session_id, resume=resume, inject_plan=(intent == "chat"))

    typing_task.cancel()

    # Delete status message, send actual response
    try:
        await status_msg.delete()
    except Exception:
        pass

    # Only mark session as "has talked to Claude" if it actually succeeded
    if not result.startswith("⚠️"):
        session.touch()
        session.qa_log.append((prompt, result))

        # Auto-flush if log is too large
        if session.qa_log_size() >= QA_LOG_FLUSH_SIZE:
            await update.message.reply_text("📦 對話記錄已達上限，自動整理中...")
            flush_result = await _flush_qa_log(session)
            if flush_result and not flush_result.startswith("⚠️"):
                await update.message.reply_text("✅ 學習筆記已自動儲存，繼續對話")

    # Split long messages (Telegram limit: 4096 chars)
    if len(result) <= 4000:
        await update.message.reply_text(result)
    else:
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i + 4000])


async def post_init(app: Application):
    """Set bot commands menu and send restart notification if applicable."""
    notify_file = REPO_DIR / ".restart_notify"
    if notify_file.exists():
        try:
            chat_id = int(notify_file.read_text().strip())
            await app.bot.send_message(chat_id, "✅ 重啟完成")
        except Exception as e:
            logger.warning(f"Failed to send restart notification: {e}")
        finally:
            notify_file.unlink(missing_ok=True)

    commands = [
        BotCommand("start", "顯示指令列表"),
        BotCommand("deep", "聊到一半需要深度思考→切 Opus 不斷對話"),
        BotCommand("plan", "規劃工作：記錄想法→Opus 拆計畫→Sonnet 實作"),
        BotCommand("course", "學習模式：Opus 帶你讀課程和做練習"),
        BotCommand("opus", "整段對話切 Opus（開新 session）"),
        BotCommand("sonnet", "切回 Sonnet（日常對話）"),
        BotCommand("morning", "今天該做什麼？讀主線+近況給建議"),
        BotCommand("evening", "日結：更新記憶/daily/README + commit"),
        BotCommand("done", "結束對話並儲存筆記"),
        BotCommand("repo", "切工作目錄：journal / kage / home"),
        BotCommand("release", "kage 發版：preview diff → 開 PR"),
        BotCommand("restart", "拉最新 code + 重啟 Bot"),
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
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("repo", cmd_repo))
    app.add_handler(CommandHandler("morning", cmd_morning))
    app.add_handler(CommandHandler("evening", cmd_evening))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CommandHandler("deep", cmd_deep))
    app.add_handler(CommandHandler("release", handle_release))
    app.add_handler(CommandHandler("course", handle_message))
    app.add_handler(CommandHandler("opus", handle_message))
    app.add_handler(CommandHandler("sonnet", handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    # Unknown commands → treat as regular text (don't silently drop)
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
