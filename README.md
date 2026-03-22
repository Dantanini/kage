# kage (影)

Personal AI assistant via Telegram — a thin relay to Claude Code CLI.

## What is this

kage is a lightweight Telegram bot that bridges your messages to [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code). Instead of building AI logic into the bot, kage keeps itself thin and delegates all intelligence to Claude Code's native capabilities — Skills, Hooks, CLAUDE.md, and tool use.

The bot automatically classifies your intent and routes to the appropriate Claude model:

| Intent | Model | Example |
|---|---|---|
| Course learning, architecture | Opus | "我想繼續學 prompt engineering" |
| Notes, summaries, commits | Sonnet | "幫我整理今天做的事" |
| Intent classification | Haiku | (internal routing, invisible to user) |

## Architecture

```
Telegram → kage (thin relay) → claude -p → your repo's .claude/ (Skills, CLAUDE.md)
                                   ↓
                              reads/writes repo files
                              git commit + push
```

Key design decisions:
- **Bot has no AI logic** — all intelligence lives in each repo's `.claude/` directory
- **Adding features = adding Skills** — no bot code changes needed
- **Model routing via Haiku** — fast intent classification, then dispatch to the right model
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

Edit `config.yaml` to customize model routing and session timeout.

### Run

```bash
python3 bot.py
```

## Commands

| Command | Description |
|---|---|
| `/start` | Start the assistant |
| `/course` | Enter course learning mode (Opus) |
| `/note` | Quick note mode (Sonnet) |
| `/done` | End session, save and commit |

You can also just type naturally — Haiku will classify your intent automatically.

## Security

Three-layer pre-commit secret protection:

1. **File blocklist** — `.env`, `*.pem`, `*.key` cannot be staged
2. **Regex scan** — detects common secret patterns in staged diffs
3. **gitleaks** — deep scan with 800+ secret patterns

## Project structure

```
kage/
├── bot.py          ← Telegram ↔ claude -p relay
├── router.py       ← Haiku intent classification + model routing
├── session.py      ← Session lifecycle management
├── config.yaml     ← Model mapping and settings
├── .githooks/
│   └── pre-commit  ← 3-layer secret scanning
└── .env.example
```

## Design philosophy

- **Thin shell** — bot is a relay, not a brain
- **Scripts for deterministic tasks** — dates, git, validation use Python scripts, not LLM
- **LLM for reasoning** — intent classification, content writing, deep discussion
- **Expandable** — add repos, add Skills, no bot refactoring needed

## License

MIT
