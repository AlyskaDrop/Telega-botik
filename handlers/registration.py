"""User registration via in-game screenshot."""

from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from database import get_db
from utils import extract_text

# Conversation states
ASK_INGAME_NAME, WAIT_SCREENSHOT = range(2)


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db = await get_db()
    row = await db.execute("SELECT id, approved FROM users WHERE id = ?", (user.id,))
    existing = await row.fetchone()
    if existing:
        status = {0: "ожидает подтверждения", 1: "подтверждён", 2: "отклонён"}.get(
            existing["approved"], "неизвестен"
        )
        await update.message.reply_text(
            f"✅ Ты уже зарегистрирован. Статус: *{status}*",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 Добро пожаловать в корпорацию *Weeping Ghosts*!\n\n"
        "Для регистрации введи своё *игровое имя* (точно как в Eve Echoes):",
        parse_mode="Markdown",
    )
    return ASK_INGAME_NAME


async def receive_ingame_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 64:
        await update.message.reply_text(
            "❌ Имя должно быть от 2 до 64 символов. Попробуй снова:"
        )
        return ASK_INGAME_NAME

    context.user_data["ingame_name"] = name
    await update.message.reply_text(
        f"Отлично, *{name}*!\n\n"
        "Теперь отправь скриншот своего профиля/характеристик персонажа в игре Eve Echoes "
        "для подтверждения личности.",
        parse_mode="Markdown",
    )
    return WAIT_SCREENSHOT


async def receive_screenshot(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    user = update.effective_user
    photo = update.message.photo[-1] if update.message.photo else None
    doc = update.message.document

    file_id: str | None = None
    if photo:
        file_id = photo.file_id
    elif doc and doc.mime_type and doc.mime_type.startswith("image/"):
        file_id = doc.file_id
    else:
        await update.message.reply_text(
            "❌ Пожалуйста, отправь изображение (фото или файл-картинку)."
        )
        return WAIT_SCREENSHOT

    ingame_name = context.user_data.get("ingame_name", "Unknown")

    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO users (id, username, ingame_name, approved) VALUES (?,?,?,0)",
        (user.id, user.username or "", ingame_name),
    )
    await db.commit()

    # Notify admins
    from config import ADMIN_IDS

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Одобрить", callback_data=f"approve_user:{user.id}"
                ),
                InlineKeyboardButton(
                    "❌ Отклонить", callback_data=f"reject_user:{user.id}"
                ),
            ]
        ]
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=(
                    f"📋 *Новая заявка на регистрацию*\n"
                    f"Telegram: @{user.username or 'N/A'} (ID: `{user.id}`)\n"
                    f"Игровое имя: *{ingame_name}*"
                ),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception:
            pass

    await update.message.reply_text(
        "📨 Заявка отправлена на рассмотрение администраторам.\n"
        "Ты получишь уведомление после проверки. Обычно это занимает до 24 часов."
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Регистрация отменена.")
    return ConversationHandler.END


async def approve_user_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split(":")[1])
    db = await get_db()
    await db.execute(
        "UPDATE users SET approved = 1 WHERE id = ?", (target_id,)
    )
    await db.commit()
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n✅ *Одобрено*",
        parse_mode="Markdown",
    )
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="🎉 Твоя заявка на вступление в *Weeping Ghosts* одобрена!\n"
            "Используй /menu для просмотра доступных команд.",
            parse_mode="Markdown",
        )
    except Exception:
        pass


async def reject_user_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split(":")[1])
    db = await get_db()
    await db.execute(
        "UPDATE users SET approved = 2 WHERE id = ?", (target_id,)
    )
    await db.commit()
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n❌ *Отклонено*",
        parse_mode="Markdown",
    )
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="😔 К сожалению, твоя заявка на вступление в *Weeping Ghosts* отклонена.\n"
            "Обратись к администраторам для уточнения причины.",
            parse_mode="Markdown",
        )
    except Exception:
        pass


def build_registration_handlers() -> list:
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_registration),
                      CommandHandler("register", start_registration)],
        states={
            ASK_INGAME_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ingame_name)
            ],
            WAIT_SCREENSHOT: [
                MessageHandler(
                    (filters.PHOTO | filters.Document.IMAGE), receive_screenshot
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    return [
        conv,
        CallbackQueryHandler(approve_user_callback, pattern=r"^approve_user:"),
        CallbackQueryHandler(reject_user_callback, pattern=r"^reject_user:"),
    ]
