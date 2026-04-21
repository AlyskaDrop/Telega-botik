"""Activity report submission via screenshot (PvP / PvE / Loot delivery)."""

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
from config import ADMIN_IDS

# Conversation states
REP_WAIT_SCREENSHOT, REP_WAIT_CATEGORY, REP_WAIT_AMOUNT = range(3)

CATEGORY_LABELS = {"pvp": "⚔️ PvP", "pve": "🛡️ PvE", "loot": "📦 Сдача лута"}


async def _require_registered(update: Update) -> bool:
    db = await get_db()
    row = await (
        await db.execute(
            "SELECT approved FROM users WHERE id=?", (update.effective_user.id,)
        )
    ).fetchone()
    if not row or row["approved"] != 1:
        await update.effective_message.reply_text(
            "⛔ Ты должен быть зарегистрированным участником корпорации.\n"
            "Используй /register для подачи заявки."
        )
        return False
    return True


async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_registered(update):
        return ConversationHandler.END
    await update.message.reply_text(
        "📸 *Отчёт об активности*\n\n"
        "Отправь скриншот из игры (убийство, получение награды или сдача лута).",
        parse_mode="Markdown",
    )
    return REP_WAIT_SCREENSHOT


async def report_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo = update.message.photo[-1] if update.message.photo else None
    doc = update.message.document

    file_id: str | None = None
    if photo:
        file_id = photo.file_id
    elif doc and doc.mime_type and doc.mime_type.startswith("image/"):
        file_id = doc.file_id
    else:
        await update.message.reply_text("❌ Отправь изображение.")
        return REP_WAIT_SCREENSHOT

    context.user_data["report_file_id"] = file_id

    # Attempt auto-classification via OCR
    try:
        file_obj = await context.bot.get_file(file_id)
        img_bytes = await file_obj.download_as_bytearray()
        from utils import extract_text, classify_screenshot
        text = extract_text(bytes(img_bytes))
        category = classify_screenshot(text)
        from utils import extract_isk_amount
        amount = extract_isk_amount(text)
        context.user_data["report_ocr_category"] = category
        context.user_data["report_ocr_amount"] = amount
    except Exception:
        category = "unknown"
        amount = 0.0

    context.user_data["report_amount"] = amount
    hint = f"\nАвто-определено: *{CATEGORY_LABELS.get(category, '❓ Не определено')}*" if category != "unknown" else ""

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚔️ PvP", callback_data="rep_cat:pvp"),
             InlineKeyboardButton("🛡️ PvE", callback_data="rep_cat:pve"),
             InlineKeyboardButton("📦 Лут", callback_data="rep_cat:loot")],
        ]
    )
    await update.message.reply_text(
        f"Выбери категорию отчёта:{hint}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return REP_WAIT_CATEGORY


async def report_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    category = query.data.split(":")[1]
    context.user_data["report_category"] = category

    pre = context.user_data.get("report_ocr_amount", 0.0)
    hint = f" (OCR: {pre:.0f})" if pre > 0 else ""
    await query.edit_message_text(
        f"Категория: *{CATEGORY_LABELS[category]}*\n\n"
        f"Введи сумму ISK{hint} (0 если неизвестно):",
        parse_mode="Markdown",
    )
    return REP_WAIT_AMOUNT


async def report_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Введи число:")
        return REP_WAIT_AMOUNT

    user = update.effective_user
    category = context.user_data["report_category"]
    file_id = context.user_data["report_file_id"]

    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO activity_reports (user_id, category, amount, screenshot) VALUES (?,?,?,?)",
        (user.id, category, amount, file_id),
    )
    await db.commit()
    report_id = cursor.lastrowid

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Одобрить", callback_data=f"adm:approve_report:{report_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"adm:reject_report:{report_id}"),
    ]])

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=(
                    f"📊 *Новый отчёт #{report_id}*\n"
                    f"Пилот: @{user.username or 'N/A'} (ID: `{user.id}`)\n"
                    f"Категория: {CATEGORY_LABELS[category]}\n"
                    f"Сумма: {amount:.0f} ISK"
                ),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception:
            pass

    await update.message.reply_text(
        f"✅ Отчёт #{report_id} отправлен на проверку администратору.\n"
        f"Категория: {CATEGORY_LABELS[category]} | Сумма: {amount:.0f} ISK"
    )
    return ConversationHandler.END


async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отчёт отменён.")
    return ConversationHandler.END


def build_report_handlers() -> list:
    conv = ConversationHandler(
        entry_points=[CommandHandler("report", report_start)],
        states={
            REP_WAIT_SCREENSHOT: [
                MessageHandler(
                    (filters.PHOTO | filters.Document.IMAGE), report_screenshot
                )
            ],
            REP_WAIT_CATEGORY: [
                CallbackQueryHandler(report_category, pattern=r"^rep_cat:")
            ],
            REP_WAIT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, report_amount)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_report)],
    )
    return [conv]
