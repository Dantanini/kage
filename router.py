"""Model 路由 — 預設 Sonnet，指令切換，工作流腳本控制。"""

# 指令 → (model, intent)
COMMAND_ROUTES: dict[str, tuple[str, str]] = {
    "/course": ("opus", "course"),
    "/opus": ("opus", "chat"),
    "/sonnet": ("sonnet", "chat"),
    "/note": ("sonnet", "note"),
    "/done": ("sonnet", "done"),
    "/restart": ("sonnet", "restart"),
    "/morning": ("sonnet", "morning"),
    "/evening": ("sonnet", "evening"),
}

DEFAULT_MODEL = "sonnet"


def route(message: str, model_map: dict[str, str] | None = None) -> tuple[str, str]:
    """Route message. Commands switch model, otherwise use default or current session model."""
    text = message.strip()

    for cmd, (model, intent) in COMMAND_ROUTES.items():
        if text.startswith(cmd):
            return model, intent

    default = (model_map or {}).get("default", DEFAULT_MODEL)
    return default, "chat"
