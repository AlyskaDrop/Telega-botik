"""Tag management: change user titles/tags in the Telegram group chat."""

from __future__ import annotations

from telegram import Update, ChatPermissions
from telegram.ext import CommandHandler, ContextTypes
from telegram.error import TelegramError

from config import ADMIN_IDS, CORP_CHAT_ID
from database import get_db


def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


# Predefined roles and their display titles
ROLE_TITLES: dict[str, str] = {
    "pilot": "🚀 Пилот",
    "fc": "🎖️ FC (Флит Командир)",
    "miner": "⛏️ Майнер",
    "industrialist": "🏭 Промышленник",
    "recruiter": "📋 Рекрутер",
    "diplomat": "🤝 Дипломат",
    "officer": "⭐ Офицер",
    "director": "🌟 Директор",
    "ceo": "👑 CEO",
}


async def set_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command: /set_tag <user_id> <role>"""
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return

    if not context.args or len(context.args) < 2:
        roles = "\n".join(f"• `{k}` — {v}" for k, v in ROLE_TITLES.items())
        await update.message.reply_text(
            f"Использование: `/set_tag <user_id> <role>`\n\nДоступные роли:\n{roles}",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя.")
        return

    role = context.args[1].lower()
    if role not in ROLE_TITLES:
        await update.message.reply_text(
            f"❌ Неизвестная роль. Доступные: {', '.join(ROLE_TITLES.keys())}"
        )
        return

    db = await get_db()
    row = await (await db.execute(
        "SELECT ingame_name FROM users WHERE id=?", (target_id,)
    )).fetchone()
    if not row:
        await update.message.reply_text("Пользователь не найден в базе.")
        return

    ingame_name = row["ingame_name"]
    await db.execute("UPDATE users SET corp_role=? WHERE id=?", (role, target_id))
    await db.commit()

    # Attempt to set custom title in the group (bot must be admin with right to set titles)
    if CORP_CHAT_ID:
        try:
            await context.bot.promote_chat_member(
                chat_id=CORP_CHAT_ID,
                user_id=target_id,
                can_change_info=False,
                can_delete_messages=False,
                can_invite_users=False,
                can_restrict_members=False,
                can_pin_messages=False,
                can_promote_members=False,
                can_manage_chat=False,
                can_manage_video_chats=False,
            )
            await context.bot.set_chat_administrator_custom_title(
                chat_id=CORP_CHAT_ID,
                user_id=target_id,
                custom_title=ROLE_TITLES[role][:16],  # Telegram limit: 16 chars
            )
        except TelegramError as e:
            await update.message.reply_text(
                f"⚠️ Роль обновлена в базе, но не удалось изменить тег в чате: {e}"
            )
            return

    await update.message.reply_text(
        f"✅ Роль *{ingame_name}* изменена на *{ROLE_TITLES[role]}*",
        parse_mode="Markdown",
    )
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🏷️ Твоя роль в корпорации изменена: *{ROLE_TITLES[role]}*",
            parse_mode="Markdown",
        )
    except Exception:
        pass


async def my_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user their current role."""
    db = await get_db()
    row = await (await db.execute(
        "SELECT ingame_name, corp_role FROM users WHERE id=?",
        (update.effective_user.id,),
    )).fetchone()
    if not row:
        await update.message.reply_text("Ты не зарегистрирован. /register")
        return
    role_label = ROLE_TITLES.get(row["corp_role"], row["corp_role"])
    await update.message.reply_text(
        f"🏷️ Твоя роль: *{role_label}*\nИгровое имя: *{row['ingame_name']}*",
        parse_mode="Markdown",
    )


def build_tag_handlers() -> list:
    return [
        CommandHandler("set_tag", set_tag),
        CommandHandler("my_tag", my_tag),
    ]
