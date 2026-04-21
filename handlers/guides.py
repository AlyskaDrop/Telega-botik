"""Beginner guides: list and view guides, admins can add new ones."""

from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from config import ADMIN_IDS
from database import get_db

# Conversation states for guide creation
GUIDE_CAT, GUIDE_TITLE, GUIDE_CONTENT = range(3)

CATEGORIES = {
    "general": "📘 Общее",
    "pvp": "⚔️ PvP",
    "pve": "🛡️ PvE",
    "industry": "🏭 Промышленность",
    "fitting": "🔧 Фиттинг",
}


async def list_guides(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = await get_db()
    rows = await (await db.execute(
        "SELECT id, title, category FROM guides ORDER BY category, id"
    )).fetchall()

    if not rows:
        await update.message.reply_text(
            "📚 Гайдов пока нет. Администраторы могут добавить через /add_guide."
        )
        return

    by_cat: dict[str, list] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)

    buttons = []
    for cat, items in by_cat.items():
        label = CATEGORIES.get(cat, cat)
        for item in items:
            buttons.append([InlineKeyboardButton(
                f"{label}: {item['title']}", callback_data=f"guide:{item['id']}"
            )])

    await update.message.reply_text(
        "📚 *Гайды для новичков Weeping Ghosts*\nВыбери гайд:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def guide_detail_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    guide_id = int(query.data.split(":")[1])
    db = await get_db()
    row = await (await db.execute(
        "SELECT title, content, category, created_at FROM guides WHERE id=?", (guide_id,)
    )).fetchone()
    if not row:
        await query.answer("Гайд не найден.", show_alert=True)
        return
    label = CATEGORIES.get(row["category"], row["category"])
    text = (
        f"*{label}: {row['title']}*\n"
        f"_Добавлен: {row['created_at'][:10]}_\n\n"
        f"{row['content']}"
    )
    # Split on paragraph boundaries to avoid breaking Markdown formatting
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in text.split("\n\n"):
        segment = para + "\n\n"
        if current_len + len(segment) > 4000 and current:
            chunks.append("".join(current).rstrip())
            current = []
            current_len = 0
        current.append(segment)
        current_len += len(segment)
    if current:
        chunks.append("".join(current).rstrip())

    for i, chunk in enumerate(chunks):
        try:
            if i == 0:
                await query.edit_message_text(chunk, parse_mode="Markdown")
            else:
                await query.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            if i == 0:
                await query.edit_message_text(chunk)
            else:
                await query.message.reply_text(chunk)


# ── Admin: add guide ──────────────────────────────────────────────────────────

def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def add_guide_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return ConversationHandler.END
    cats = "\n".join(f"• `{k}` — {v}" for k, v in CATEGORIES.items())
    await update.message.reply_text(
        f"📝 *Добавление гайда*\nВведи категорию:\n{cats}",
        parse_mode="Markdown",
    )
    return GUIDE_CAT


async def guide_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cat = update.message.text.strip().lower()
    if cat not in CATEGORIES:
        await update.message.reply_text("❌ Неверная категория. Попробуй снова:")
        return GUIDE_CAT
    context.user_data["guide_cat"] = cat
    await update.message.reply_text("Введи заголовок гайда:")
    return GUIDE_TITLE


async def guide_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["guide_title"] = update.message.text.strip()
    await update.message.reply_text("Введи текст гайда (поддерживается Markdown):")
    return GUIDE_CONTENT


async def guide_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    db = await get_db()
    row = await (await db.execute("SELECT id FROM users WHERE id=?", (uid,))).fetchone()
    if not row:
        await db.execute(
            "INSERT OR IGNORE INTO users (id, username, ingame_name, approved) VALUES (?,?,?,1)",
            (uid, update.effective_user.username or "", "Admin"),
        )
        await db.commit()

    cursor = await db.execute(
        "INSERT INTO guides (title, content, category, author_id) VALUES (?,?,?,?)",
        (
            context.user_data["guide_title"],
            update.message.text.strip(),
            context.user_data["guide_cat"],
            uid,
        ),
    )
    await db.commit()
    await update.message.reply_text(f"✅ Гайд #{cursor.lastrowid} добавлен!")
    return ConversationHandler.END


async def cancel_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def build_guides_handlers() -> list:
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add_guide", add_guide_start)],
        states={
            GUIDE_CAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, guide_category)],
            GUIDE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, guide_title)],
            GUIDE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, guide_content)],
        },
        fallbacks=[CommandHandler("cancel", cancel_guide)],
    )
    return [
        CommandHandler("guides", list_guides),
        add_conv,
        CallbackQueryHandler(guide_detail_callback, pattern=r"^guide:"),
    ]
