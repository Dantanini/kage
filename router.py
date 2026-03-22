"""意圖分類 + model 路由。"""

import asyncio
import subprocess
import shutil
from pathlib import Path

# 指令 → 意圖對應
COMMAND_MAP: dict[str, str] = {
    "/course": "course",
    "/note": "note",
    "/done": "done",
    "/decide": "decision",
}

# 意圖 → model 對應（從 config.yaml 載入，這裡是 fallback）
MODEL_MAP: dict[str, str] = {
    "course": "opus",
    "architecture": "opus",
    "decision": "opus",
    "note": "sonnet",
    "commit": "sonnet",
    "summary": "sonnet",
    "done": "sonnet",
    "chat": "sonnet",
}

CLASSIFY_PROMPT = """你是一個意圖分類器。根據以下訊息，回傳一個詞代表意圖類別。
只回傳類別名稱，不要其他文字。

類別：course（課程學習）, note（記筆記）, decision（做決定）, architecture（架構討論）, chat（閒聊）, end（結束對話）

訊息：{message}"""


def _find_claude() -> str:
    """Find claude CLI binary path, cross-platform."""
    claude = shutil.which("claude")
    if claude:
        return claude
    # Common install locations
    candidates = [
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / ".claude" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise FileNotFoundError("claude CLI not found. Is Claude Code installed?")


async def classify(message: str) -> str:
    """Use Haiku to classify message intent."""
    claude_bin = _find_claude()
    prompt = CLASSIFY_PROMPT.format(message=message[:200])  # limit input

    proc = await asyncio.create_subprocess_exec(
        claude_bin, "-p", "--model", "haiku", prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    result = stdout.decode().strip().lower()

    # Normalize to known intents
    for intent in MODEL_MAP:
        if intent in result:
            return intent
    return "chat"


def route_command(message: str) -> tuple[str, str] | None:
    """Check if message is a command. Returns (model, intent) or None."""
    text = message.strip()
    for cmd, intent in COMMAND_MAP.items():
        if text.startswith(cmd):
            model = MODEL_MAP.get(intent, "sonnet")
            return model, intent
    return None


async def route(message: str, model_map: dict[str, str] | None = None) -> tuple[str, str]:
    """Route message to appropriate model and intent.

    Returns (model, intent).
    """
    _map = model_map or MODEL_MAP

    # Commands take priority
    cmd_result = route_command(message)
    if cmd_result:
        return cmd_result

    # Natural language → Haiku classification
    intent = await classify(message)
    model = _map.get(intent, _map.get("default", "sonnet"))
    return model, intent
