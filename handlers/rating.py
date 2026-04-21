"""Rating leaderboards: PvP / PvE / Industry."""

from __future__ import annotations

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_db


async def pvp_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = await get_db()
    rows = await (await db.execute(
        "SELECT ingame_name, pvp_score FROM users WHERE approved=1 ORDER BY pvp_score DESC LIMIT 15"
    )).fetchall()
    await _send_rating(update, "⚔️ PvP Рейтинг", rows, "pvp_score")


async def pve_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = await get_db()
    rows = await (await db.execute(
        "SELECT ingame_name, pve_score FROM users WHERE approved=1 ORDER BY pve_score DESC LIMIT 15"
    )).fetchall()
    await _send_rating(update, "🛡️ PvE Рейтинг", rows, "pve_score")


async def industry_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = await get_db()
    rows = await (await db.execute(
        "SELECT ingame_name, industry_score FROM users WHERE approved=1 "
        "ORDER BY industry_score DESC LIMIT 15"
    )).fetchall()
    await _send_rating(update, "🏭 Промышленность Рейтинг", rows, "industry_score")


MEDALS = ["🥇", "🥈", "🥉"]


async def _send_rating(update: Update, title: str, rows, col: str) -> None:
    if not rows:
        await update.message.reply_text(f"{title}: нет данных.")
        return
    lines = [f"*{title}*\n"]
    for i, r in enumerate(rows):
        medal = MEDALS[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} {r['ingame_name']} — {r[col]}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def build_rating_handlers() -> list:
    return [
        CommandHandler("pvp_rating", pvp_rating),
        CommandHandler("pve_rating", pve_rating),
        CommandHandler("industry_rating", industry_rating),
    ]
