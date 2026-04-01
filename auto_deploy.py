#!/usr/bin/env python3
"""auto_deploy.py — Cron-triggered auto deploy from origin/main.

Runs at 03:00 daily. Checks for new commits, verifies bot is idle,
then pulls, restarts, and sends Telegram notification.

Usage (cron):
    0 3 * * * cd /home/dantanini/kage && python3 auto_deploy.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from tg_notify import send_telegram_message

# --- Config ---

REPO_DIR = Path(__file__).resolve().parent
LAST_ACTIVITY_FILE = REPO_DIR / ".last_activity"
IDLE_MINUTES = 30
LOG_FILE = REPO_DIR / "logs" / "auto_deploy.log"


def load_env():
    """Load .env file into environment."""
    env_path = REPO_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


def run_git(*args: str) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True, text=True, check=True,
        cwd=REPO_DIR,
    )
    return result.stdout.strip()


def has_new_commits(branch: str = "main") -> bool:
    """Check if origin/main has commits not in local main."""
    try:
        run_git("fetch", "origin", branch)
        log = run_git("log", f"{branch}..origin/{branch}", "--oneline")
        return bool(log)
    except (RuntimeError, subprocess.CalledProcessError):
        return False


def is_bot_idle(
    ts_file: Path | None = None,
    idle_minutes: int = IDLE_MINUTES,
) -> bool:
    """Check if bot has no active session based on last activity timestamp."""
    if ts_file is None:
        ts_file = LAST_ACTIVITY_FILE

    if not ts_file.exists():
        return True

    try:
        last_ts = float(ts_file.read_text().strip())
    except (ValueError, OSError):
        return True

    elapsed = time.time() - last_ts
    return elapsed > idle_minutes * 60


def build_notify_message(
    success: bool | None = True,
    commits_summary: str = "",
    error: str = "",
    reason: str = "",
) -> str:
    """Build Telegram notification message."""
    if success is None:
        return f"⏭ Deploy skipped: {reason}"
    if success:
        return f"✓ Auto-deploy 完成\n{commits_summary}"
    return f"✗ Auto-deploy 失敗: {error}"


def send_telegram(message: str):
    """Send notification via Telegram Bot API."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    admin_id = os.environ.get("TELEGRAM_ADMIN_ID", "")
    send_telegram_message(message, token=token, chat_id=admin_id)


def log(msg: str):
    """Append to log file."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")


def deploy():
    """Pull latest main, restart bot."""
    run_git("checkout", "main")
    run_git("pull", "origin", "main")

    # Get summary of what was deployed
    summary = run_git("log", "--oneline", "-5")

    # Restart bot via systemd
    subprocess.run(
        ["systemctl", "--user", "restart", "kage"],
        check=True,
    )
    return summary


def main():
    load_env()

    log("Auto-deploy check started")

    # 1. Check for new commits
    if not has_new_commits():
        log("No new commits, skipping")
        return

    # 2. Check if bot is idle
    if not is_bot_idle():
        msg = build_notify_message(success=None, reason="bot is active")
        log(msg)
        send_telegram(msg)
        return

    # 3. Deploy
    try:
        summary = deploy()
        msg = build_notify_message(success=True, commits_summary=summary)
        log(msg)
        send_telegram(msg)
    except Exception as e:
        msg = build_notify_message(success=False, error=str(e))
        log(msg)
        send_telegram(msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
