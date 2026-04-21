"""Admin panel: manage users, balance adjustments, report approvals."""

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

# Conversation states
ADM_AWAIT_BALANCE_USER, ADM_AWAIT_BALANCE_AMOUNT, ADM_AWAIT_BALANCE_REASON = range(3)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_only(func):
    """Decorator: silently ignore non-admins."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not _is_admin(update.effective_user.id):
            await update.effective_message.reply_text("⛔ Нет доступа.")
            return
        return await func(update, context)
    return wrapper


@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👥 Все пользователи", callback_data="adm:users")],
            [InlineKeyboardButton("⏳ Заявки на регистрацию", callback_data="adm:pending")],
            [InlineKeyboardButton("📊 Неподтверждённые отчёты", callback_data="adm:reports")],
            [InlineKeyboardButton("💰 Скорректировать баланс", callback_data="adm:balance")],
            [InlineKeyboardButton("📋 Управление заказами", callback_data="adm:orders")],
        ]
    )
    await update.message.reply_text(
        "🛡️ *Панель администратора — Weeping Ghosts*", 
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return
    await query.answer()

    action = query.data.split(":", 1)[1]

    if action == "users":
        db = await get_db()
        rows = await (await db.execute(
            "SELECT id, username, ingame_name, corp_role, balance, approved FROM users LIMIT 50"
        )).fetchall()
        if not rows:
            await query.edit_message_text("Пользователей нет.")
            return
        lines = ["👥 *Список пользователей:*\n"]
        for r in rows:
            status = {0: "⏳", 1: "✅", 2: "❌"}.get(r["approved"], "?")
            lines.append(
                f"{status} `{r['id']}` — *{r['ingame_name']}* "
                f"(@{r['username'] or 'N/A'}) | {r['corp_role']} | {r['balance']:.0f} ISK"
            )
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")

    elif action == "pending":
        db = await get_db()
        rows = await (await db.execute(
            "SELECT id, username, ingame_name FROM users WHERE approved = 0"
        )).fetchall()
        if not rows:
            await query.edit_message_text("Нет ожидающих заявок ✅")
            return
        lines = ["⏳ *Ожидают подтверждения:*\n"]
        for r in rows:
            lines.append(f"• `{r['id']}` — *{r['ingame_name']}* (@{r['username'] or 'N/A'})")
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅", callback_data=f"approve_user:{r['id']}"),
                InlineKeyboardButton("❌", callback_data=f"reject_user:{r['id']}"),
            ]])
        await query.edit_message_text(
            "\n".join(lines), parse_mode="Markdown", reply_markup=keyboard
        )

    elif action == "reports":
        db = await get_db()
        rows = await (await db.execute(
            "SELECT ar.id, u.ingame_name, ar.category, ar.amount, ar.created_at "
            "FROM activity_reports ar JOIN users u ON ar.user_id=u.id "
            "WHERE ar.approved=0 ORDER BY ar.created_at DESC LIMIT 20"
        )).fetchall()
        if not rows:
            await query.edit_message_text("Нет неподтверждённых отчётов ✅")
            return
        lines = ["📊 *Неподтверждённые отчёты:*\n"]
        buttons = []
        for r in rows:
            lines.append(
                f"ID {r['id']} | {r['ingame_name']} | {r['category'].upper()} | "
                f"{r['amount']:.0f} ISK | {r['created_at'][:10]}"
            )
            buttons.append([
                InlineKeyboardButton(f"✅ #{r['id']}", callback_data=f"adm:approve_report:{r['id']}"),
                InlineKeyboardButton(f"❌ #{r['id']}", callback_data=f"adm:reject_report:{r['id']}"),
            ])
        await query.edit_message_text(
            "\n".join(lines), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    elif action == "balance":
        context.user_data["adm_action"] = "balance"
        await query.edit_message_text(
            "Введи Telegram ID пользователя для изменения баланса:"
        )
        return ADM_AWAIT_BALANCE_USER

    elif action.startswith("approve_report:"):
        report_id = int(action.split(":")[1])
        db = await get_db()
        row = await (await db.execute(
            "SELECT user_id, category, amount FROM activity_reports WHERE id=?", (report_id,)
        )).fetchone()
        if row:
            await db.execute("UPDATE activity_reports SET approved=1 WHERE id=?", (report_id,))
            col = {"pvp": "pvp_score", "pve": "pve_score", "loot": "industry_score"}.get(
                row["category"], "industry_score"
            )
            # col is constrained to known safe column names from the dict above
            assert col in ("pvp_score", "pve_score", "industry_score")
            if col == "pvp_score":
                await db.execute(
                    "UPDATE users SET pvp_score = pvp_score + ?, balance = balance + ? WHERE id = ?",
                    (int(row["amount"] // 1000), row["amount"], row["user_id"]),
                )
            elif col == "pve_score":
                await db.execute(
                    "UPDATE users SET pve_score = pve_score + ?, balance = balance + ? WHERE id = ?",
                    (int(row["amount"] // 1000), row["amount"], row["user_id"]),
                )
            else:
                await db.execute(
                    "UPDATE users SET industry_score = industry_score + ?, balance = balance + ? WHERE id = ?",
                    (int(row["amount"] // 1000), row["amount"], row["user_id"]),
                )
            await db.commit()
            await query.answer(f"✅ Отчёт #{report_id} одобрен")
        else:
            await query.answer("Отчёт не найден", show_alert=True)

    elif action.startswith("reject_report:"):
        report_id = int(action.split(":")[1])
        db = await get_db()
        await db.execute("UPDATE activity_reports SET approved=2 WHERE id=?", (report_id,))
        await db.commit()
        await query.answer(f"❌ Отчёт #{report_id} отклонён")

    elif action == "orders":
        db = await get_db()
        rows = await (await db.execute(
            "SELECT id, title, status, reward FROM orders ORDER BY created_at DESC LIMIT 20"
        )).fetchall()
        if not rows:
            await query.edit_message_text("Заказов нет.")
            return
        lines = ["📋 *Заказы:*\n"]
        for r in rows:
            lines.append(f"#{r['id']} [{r['status']}] {r['title']} — {r['reward']:.0f} ISK")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")


# ── Balance adjustment conversation ───────────────────────────────────────────

@admin_only
async def balance_adjust_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.message.reply_text(
        "Введи Telegram ID пользователя для изменения баланса:"
    )
    return ADM_AWAIT_BALANCE_USER


async def balance_user_received(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Неверный ID. Введи число:")
        return ADM_AWAIT_BALANCE_USER
    db = await get_db()
    row = await (await db.execute(
        "SELECT ingame_name FROM users WHERE id=?", (uid,)
    )).fetchone()
    if not row:
        await update.message.reply_text("Пользователь не найден. Введи другой ID:")
        return ADM_AWAIT_BALANCE_USER
    context.user_data["balance_target"] = uid
    await update.message.reply_text(
        f"Пользователь: *{row['ingame_name']}*\nВведи сумму (положительную или отрицательную):",
        parse_mode="Markdown",
    )
    return ADM_AWAIT_BALANCE_AMOUNT


async def balance_amount_received(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    try:
        amount = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Неверная сумма. Введи число:")
        return ADM_AWAIT_BALANCE_AMOUNT
    context.user_data["balance_amount"] = amount
    await update.message.reply_text("Введи причину изменения баланса:")
    return ADM_AWAIT_BALANCE_REASON


async def balance_reason_received(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    reason = update.message.text.strip()
    uid = context.user_data["balance_target"]
    amount = context.user_data["balance_amount"]
    admin_id = update.effective_user.id

    db = await get_db()
    await db.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, uid))
    await db.execute(
        "INSERT INTO transactions (user_id, delta, reason, admin_id) VALUES (?,?,?,?)",
        (uid, amount, reason, admin_id),
    )
    await db.commit()

    row = await (await db.execute("SELECT balance, ingame_name FROM users WHERE id=?", (uid,))).fetchone()
    sign = "+" if amount >= 0 else ""
    await update.message.reply_text(
        f"✅ Баланс *{row['ingame_name']}* изменён на {sign}{amount:.0f} ISK\n"
        f"Текущий баланс: {row['balance']:.0f} ISK\nПричина: {reason}",
        parse_mode="Markdown",
    )
    try:
        await update.get_bot().send_message(
            chat_id=uid,
            text=f"💰 Изменение баланса: *{sign}{amount:.0f} ISK*\nПричина: {reason}\n"
                 f"Текущий баланс: *{row['balance']:.0f} ISK*",
            parse_mode="Markdown",
        )
    except Exception:
        pass
    return ConversationHandler.END


async def cancel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END


def build_admin_handlers() -> list:
    balance_conv = ConversationHandler(
        entry_points=[CommandHandler("balance_adjust", balance_adjust_start)],
        states={
            ADM_AWAIT_BALANCE_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_user_received)
            ],
            ADM_AWAIT_BALANCE_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_amount_received)
            ],
            ADM_AWAIT_BALANCE_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_reason_received)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_admin)],
    )
    return [
        CommandHandler("admin", admin_panel),
        CallbackQueryHandler(admin_callback, pattern=r"^adm:"),
        balance_conv,
    ]
