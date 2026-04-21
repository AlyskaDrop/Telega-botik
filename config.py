"""Bot configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.environ["BOT_TOKEN"]

# Space-separated list of Telegram user IDs that have admin rights
ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split() if x
]

# The Telegram chat/group ID where the corporation operates
CORP_CHAT_ID: int = int(os.getenv("CORP_CHAT_ID", "0"))

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "data/bot.db")

# ── OCR ───────────────────────────────────────────────────────────────────────
TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", "tesseract")
