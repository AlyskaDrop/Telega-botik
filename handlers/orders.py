"""Corp orders: list, create, take, and complete orders."""

from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import ADMIN_IDS
from database import get_db

# Conversation states for order creation
ORD_TITLE, ORD_DESC, ORD_REWARD = range(3)

STATUS_EMOJI = {"open": "🟢", "in_progress": "🟡", "done": "✅", "cancelled": "❌"}


def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def list_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = await get_db()
    rows = await (await db.execute(
        "SELECT id, title, description, reward, status, assigned_to "
        "FROM orders WHERE status IN ('open','in_progress') ORDER BY created_at DESC LIMIT 20"
    )).fetchall()

    if not rows:
        await update.message.reply_text("📋 Активных заказов нет.")
        return

    buttons = []
    lines = ["📋 *Доступные заказы:*\n"]
    for r in rows:
        emoji = STATUS_EMOJI.get(r["status"], "•")
        lines.append(f"{emoji} *#{r['id']}* {r['title']} — {r['reward']:.0f} ISK")
        if r["status"] == "open":
            buttons.append([InlineKeyboardButton(
                f"Взять #{r['id']}", callback_data=f"ord:take:{r['id']}"
            )])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
    )


async def order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /order <ID>")
        return
    try:
        oid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный ID.")
        return

    db = await get_db()
    row = await (await db.execute(
        "SELECT o.*, u.ingame_name AS creator_name FROM orders o "
        "JOIN users u ON o.created_by=u.id WHERE o.id=?", (oid,)
    )).fetchone()
    if not row:
        await update.message.reply_text("Заказ не найден.")
        return

    emoji = STATUS_EMOJI.get(row["status"], "•")
    text = (
        f"{emoji} *Заказ #{row['id']}*\n"
        f"*{row['title']}*\n\n"
        f"{row['description'] or '_Описание не указано_'}\n\n"
        f"💰 Награда: {row['reward']:.0f} ISK\n"
        f"📅 Создан: {row['created_at'][:10]}\n"
        f"👤 Создал: {row['creator_name']}"
    )
    buttons = []
    if row["status"] == "open":
        buttons.append([InlineKeyboardButton("📌 Взять заказ", callback_data=f"ord:take:{oid}")])
    elif row["status"] == "in_progress" and row["assigned_to"] == update.effective_user.id:
        buttons.append([InlineKeyboardButton("✅ Завершить", callback_data=f"ord:done:{oid}")])

    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
    )


async def order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action, oid = parts[1], int(parts[2])
    uid = query.from_user.id

    db = await get_db()
    row = await (await db.execute(
        "SELECT status, assigned_to, title FROM orders WHERE id=?", (oid,)
    )).fetchone()
    if not row:
        return

    if action == "take":
        if row["status"] != "open":
            await query.answer("Заказ уже взят или недоступен.", show_alert=True)
            return
        user_row = await (await db.execute(
            "SELECT approved FROM users WHERE id=?", (uid,)
        )).fetchone()
        if not user_row or user_row["approved"] != 1:
            await query.answer("⛔ Только подтверждённые участники могут брать заказы.", show_alert=True)
            return
        await db.execute(
            "UPDATE orders SET status='in_progress', assigned_to=?, updated_at=datetime('now') WHERE id=?",
            (uid, oid),
        )
        await db.commit()
        await query.edit_message_text(
            f"📌 Ты взял заказ *#{oid}: {row['title']}*\n"
            f"Используй /order {oid} → 'Завершить' когда выполнишь.",
            parse_mode="Markdown",
        )

    elif action == "done":
        if row["status"] != "in_progress" or row["assigned_to"] != uid:
            await query.answer("Недоступно.", show_alert=True)
            return
        await db.execute(
            "UPDATE orders SET status='done', updated_at=datetime('now') WHERE id=?", (oid,)
        )
        # Give reward
        reward_row = await (await db.execute("SELECT reward FROM orders WHERE id=?", (oid,))).fetchone()
        if reward_row:
            await db.execute("UPDATE users SET balance=balance+? WHERE id=?", (reward_row["reward"], uid))
            await db.execute(
                "INSERT INTO transactions (user_id, delta, reason) VALUES (?,?,?)",
                (uid, reward_row["reward"], f"Выполнен заказ #{oid}"),
            )
        await db.commit()
        await query.edit_message_text(
            f"✅ Заказ *#{oid}* завершён! Награда начислена на баланс.",
            parse_mode="Markdown",
        )


# ── Admin: create order ───────────────────────────────────────────────────────

async def create_order_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return ConversationHandler.END
    await update.message.reply_text("📋 *Создание нового заказа*\nВведи заголовок:", parse_mode="Markdown")
    return ORD_TITLE


async def order_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["ord_title"] = update.message.text.strip()
    await update.message.reply_text("Введи описание (или отправь '-' чтобы пропустить):")
    return ORD_DESC


async def order_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["ord_desc"] = None if text == "-" else text
    await update.message.reply_text("Введи сумму награды в ISK:")
    return ORD_REWARD


async def order_reward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        reward = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Введи число:")
        return ORD_REWARD

    uid = update.effective_user.id
    db = await get_db()
    # Ensure admin is in users table
    row = await (await db.execute("SELECT id FROM users WHERE id=?", (uid,))).fetchone()
    if not row:
        await db.execute(
            "INSERT OR IGNORE INTO users (id, username, ingame_name, approved) VALUES (?,?,?,1)",
            (uid, update.effective_user.username or "", "Admin"),
        )
        await db.commit()

    cursor = await db.execute(
        "INSERT INTO orders (title, description, reward, created_by) VALUES (?,?,?,?)",
        (context.user_data["ord_title"], context.user_data.get("ord_desc"), reward, uid),
    )
    await db.commit()
    await update.message.reply_text(
        f"✅ Заказ *#{cursor.lastrowid}* создан!", parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def build_order_handlers() -> list:
    create_conv = ConversationHandler(
        entry_points=[CommandHandler("create_order", create_order_start)],
        states={
            ORD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_title)],
            ORD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_desc)],
            ORD_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_reward)],
        },
        fallbacks=[CommandHandler("cancel", cancel_order)],
    )
    return [
        CommandHandler("orders", list_orders),
        CommandHandler("order", order_detail),
        create_conv,
        CallbackQueryHandler(order_callback, pattern=r"^ord:"),
    ]
