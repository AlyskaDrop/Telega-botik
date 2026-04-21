"""Balance: view personal balance and transaction history."""

from __future__ import annotations

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_db


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db = await get_db()
    row = await (await db.execute(
        "SELECT ingame_name, balance, approved FROM users WHERE id=?", (user.id,)
    )).fetchone()

    if not row:
        await update.message.reply_text(
            "Ты не зарегистрирован. Используй /register."
        )
        return

    if row["approved"] != 1:
        await update.message.reply_text("⛔ Твой аккаунт ещё не подтверждён.")
        return

    txns = await (await db.execute(
        "SELECT delta, reason, created_at FROM transactions "
        "WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
        (user.id,),
    )).fetchall()

    lines = [
        f"💰 *Баланс: {row['balance']:.0f} ISK*",
        f"Пилот: *{row['ingame_name']}*\n",
        "📜 *Последние транзакции:*",
    ]
    if txns:
        for t in txns:
            sign = "+" if t["delta"] >= 0 else ""
            lines.append(
                f"{sign}{t['delta']:.0f} ISK — {t['reason'] or 'без причины'} "
                f"({t['created_at'][:10]})"
            )
    else:
        lines.append("_Транзакций нет_")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def build_balance_handlers() -> list:
    return [CommandHandler("balance", balance_cmd)]
