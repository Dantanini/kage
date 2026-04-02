# kage (影)

Personal AI assistant via Telegram — a thin relay to Claude Code CLI.

## What is this

kage is a lightweight Telegram bot that bridges your messages to [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code). Instead of building AI logic into the bot, kage keeps itself thin and delegates all intelligence to Claude Code's native capabilities — Skills, Hooks, CLAUDE.md, and tool use.

## Architecture

```
Telegram → kage (thin relay) → claude -p --permission-mode bypassPermissions
                                   ↓
                              works in selected repo's directory
                              reads repo's .claude/CLAUDE.md
                              reads/writes repo files
                              git commit + push
```

Key design decisions:
- **Bot has no AI logic** — all intelligence lives in each repo's `.claude/` directory
- **Adding features = adding Skills** — no bot code changes needed
- **Multi-repo** — switch working directory with `/repo` command
- **Session management** — conversations persist within a session, with 30-min timeout
- **Cross-platform** — runs on Linux, macOS, Windows

## Setup

### Prerequisites

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Install

```bash
git clone https://github.com/Dantanini/kage.git
cd kage
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
```

### Configure

Edit `.env`:

```
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_ADMIN_ID=your-telegram-user-id
DEV_JOURNAL_PATH=/path/to/your/repo
```

### Run

```bash
# Recommended: use systemd
cp kage.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now kage

# Or run directly
python3 bot.py
```

## Commands

| Command | Description |
|---|---|
| `/start` | Start the assistant |
| `/course` | Course learning mode (Opus) |
| `/opus` | Switch to Opus (deep thinking) |
| `/sonnet` | Switch to Sonnet (daily chat) |
| `/repo` | Show/switch working directory |
| `/repo kage` | Switch to bot's own repo |
| `/repo journal` | Switch to dev-journal |
| `/repo home` | Switch to home directory |
| `/morning` | Daily priorities summary (Opus) |
| `/evening` | Daily wrap-up + commit (Opus) |
| `/done` | End session, trigger save flow |
| `/release` | Release PR preview (develop→main) with inline confirm button |
| `/restart` | Restart bot remotely |

Just type naturally for conversation — defaults to Sonnet.

## Daily notifications

Cron sends inline-button notifications at 8am and 10pm. Tap the button to trigger Claude; ignore to save tokens.

```
0 8  * * * python3 /path/to/kage/scripts/notify.py morning
0 22 * * * python3 /path/to/kage/scripts/notify.py evening
```

## Security

- **Auth** — only admin user can interact; strangers are silently ignored
- **Three-layer pre-commit secret scan** — file blocklist, regex, gitleaks (800+ patterns)
- **Pre-push hook** — blocks force push to protected branches
- **No bot username in code** — not discoverable from public repo

## Project structure

```
kage/
├── bot.py              ← Telegram ↔ claude -p relay
├── router.py           ← Command routing (no LLM, pure Python)
├── session.py          ← Session lifecycle management + hooks
├── memory.py           ← Persistent memory layer (reads/writes dev-journal)
├── workflows.py        ← Code-defined multi-step workflow chains
├── config.yaml         ← Session timeout settings
├── scripts/
│   ├── restart.sh      ← Safe bot restart (kills rogue processes)
│   └── notify.py       ← Cron notification with inline buttons
├── tests/              ← pytest test suite (117 tests)
├── .github/workflows/  ← GitHub Actions CI
├── .claude/
│   └── CLAUDE.md       ← Operational rules for developers
├── .githooks/
│   ├── pre-commit      ← 3-layer secret scanning
│   └── pre-push        ← Block force push
└── .env.example
```

## Design philosophy

- **Thin shell** — bot is a relay, not a brain
- **Scripts for deterministic tasks** — restart, notifications, git ops use scripts, not LLM
- **LLM for reasoning** — content writing, learning, deep discussion
- **Expandable** — add repos, add Skills, no bot refactoring needed
- **Persistent memory** — auto-saves conversation context to dev-journal, injected into next session
- **Code-defined workflows** — multi-step chains with per-step model selection (sonnet for gathering, opus for synthesis)

## License

MIT
