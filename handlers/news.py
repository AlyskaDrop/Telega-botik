"""News broadcast: admins create news, bot sends to all approved users via DM."""

from __future__ import annotations

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import ADMIN_IDS
from database import get_db

NEWS_TITLE, NEWS_BODY = range(2)


def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def send_news_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return ConversationHandler.END
    await update.message.reply_text(
        "📰 *Создание новости*\nВведи заголовок:", parse_mode="Markdown"
    )
    return NEWS_TITLE


async def news_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["news_title"] = update.message.text.strip()
    await update.message.reply_text("Введи текст новости:")
    return NEWS_BODY


async def news_body(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    title = context.user_data["news_title"]
    body = update.message.text.strip()

    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO news (title, body, author_id) VALUES (?,?,?)", (title, body, uid)
    )
    news_id = cursor.lastrowid
    await db.commit()

    # Broadcast
    rows = await (await db.execute(
        "SELECT id FROM users WHERE approved=1"
    )).fetchall()

    sent = 0
    failed = 0
    for r in rows:
        try:
            await context.bot.send_message(
                chat_id=r["id"],
                text=(
                    f"📰 *{title}*\n\n{body}\n\n"
                    "_— Weeping Ghosts Corp_"
                ),
                parse_mode="Markdown",
            )
            sent += 1
        except Exception:
            failed += 1

    await db.execute("UPDATE news SET sent=1 WHERE id=?", (news_id,))
    await db.commit()

    await update.message.reply_text(
        f"✅ Новость разослана!\n📨 Доставлено: {sent} | ❌ Не доставлено: {failed}"
    )
    return ConversationHandler.END


async def cancel_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def build_news_handlers() -> list:
    conv = ConversationHandler(
        entry_points=[CommandHandler("send_news", send_news_start)],
        states={
            NEWS_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, news_title)],
            NEWS_BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, news_body)],
        },
        fallbacks=[CommandHandler("cancel", cancel_news)],
    )
    return [conv]
