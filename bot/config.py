"""
Configuration loader for Weeping Ghosts Discord Bot.
All settings are read from environment variables (or .env via python-dotenv).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Discord ────────────────────────────────────────────────────────────────────
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
GUILD_ID: int = int(os.getenv("GUILD_ID", "0"))

# ── OpenAI ─────────────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── Roles ──────────────────────────────────────────────────────────────────────
MEMBER_ROLE_ID: int = int(os.getenv("MEMBER_ROLE_ID", "0"))
VERIFIED_ROLE_ID: int = int(os.getenv("VERIFIED_ROLE_ID", "0"))
ADMIN_ROLE_ID: int = int(os.getenv("ADMIN_ROLE_ID", "0"))

# Reward role thresholds  {required_isk: role_id}
REWARD_ROLES: dict[int, int] = {}
raw_reward = os.getenv("REWARD_ROLES", "")          # "1000000:123456,5000000:789012"
for pair in raw_reward.split(","):
    pair = pair.strip()
    if ":" in pair:
        isk_str, role_str = pair.split(":", 1)
        try:
            REWARD_ROLES[int(isk_str)] = int(role_str)
        except ValueError:
            pass

# ── Channels ───────────────────────────────────────────────────────────────────
REGISTRATION_CHANNEL_ID: int = int(os.getenv("REGISTRATION_CHANNEL_ID", "0"))
KILLBOARD_CHANNEL_ID: int = int(os.getenv("KILLBOARD_CHANNEL_ID", "0"))
LOG_CHANNEL_ID: int = int(os.getenv("LOG_CHANNEL_ID", "0"))

# ── Database ───────────────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "data/weeping_ghosts.db")

# ── OCR / Vision ───────────────────────────────────────────────────────────────
# Set to "openai" to use GPT-4o Vision, or "tesseract" for local Tesseract
OCR_BACKEND: str = os.getenv("OCR_BACKEND", "openai")

# ── Compensation ───────────────────────────────────────────────────────────────
# Default ship loss compensation multiplier (0.8 = 80 % of verified ship value)
COMPENSATION_RATE: float = float(os.getenv("COMPENSATION_RATE", "0.8"))
