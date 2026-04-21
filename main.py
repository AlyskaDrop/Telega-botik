"""
Weeping Ghosts Corp Bot — Eve Echoes
Entry point: starts the bot with all handlers registered.
"""

from __future__ import annotations

import logging

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from handlers import (
    build_registration_handlers,
    build_admin_handlers,
    build_report_handlers,
    build_balance_handlers,
    build_order_handlers,
    build_rating_handlers,
    build_calculator_handlers,
    build_guides_handlers,
    build_news_handlers,
    build_tag_handlers,
    build_ai_handlers,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── /menu command ─────────────────────────────────────────────────────────────

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👾 *Weeping Ghosts Corp Bot — Eve Echoes*\n\n"
        "📋 *Основные команды:*\n"
        "/register — Регистрация в корпорации\n"
        "/balance — Мой баланс\n"
        "/report — Сдать отчёт (PvP/PvE/Лут)\n"
        "/orders — Список заказов\n"
        "/my\\_tag — Моя роль\n\n"
        "📊 *Рейтинги:*\n"
        "/pvp\\_rating — Рейтинг PvP\n"
        "/pve\\_rating — Рейтинг PvE\n"
        "/industry\\_rating — Рейтинг промышленности\n\n"
        "🧮 *Калькуляторы:*\n"
        "/industry\\_calc — Калькулятор производства\n"
        "/implant\\_calc — Калькулятор прокачки имплантов\n\n"
        "📚 *Гайды:*\n"
        "/guides — Список гайдов для новичков\n\n"
        "🤖 *AI-агент:*\n"
        "/ai <вопрос> — Задать вопрос об Eve Echoes\n"
        "? <вопрос> — Быстрый вопрос AI\n\n"
        "🛡️ *Для администраторов:*\n"
        "/admin — Панель управления\n"
        "/set\\_tag — Назначить роль пилоту\n"
        "/create\\_order — Создать заказ\n"
        "/add\\_guide — Добавить гайд\n"
        "/send\\_news — Разослать новости\n"
        "/balance\\_adjust — Изменить баланс пилота",
        parse_mode="Markdown",
    )


# ── Bot commands list (shown in "/" menu of Telegram) ─────────────────────────

BOT_COMMANDS = [
    BotCommand("start", "Регистрация / Приветствие"),
    BotCommand("menu", "Список команд"),
    BotCommand("register", "Зарегистрироваться"),
    BotCommand("balance", "Мой баланс"),
    BotCommand("report", "Сдать отчёт (PvP/PvE/Лут)"),
    BotCommand("orders", "Список заказов"),
    BotCommand("order", "Детали заказа"),
    BotCommand("my_tag", "Моя роль"),
    BotCommand("pvp_rating", "Рейтинг PvP"),
    BotCommand("pve_rating", "Рейтинг PvE"),
    BotCommand("industry_rating", "Рейтинг промышленности"),
    BotCommand("industry_calc", "Калькулятор производства"),
    BotCommand("implant_calc", "Калькулятор прокачки имплантов"),
    BotCommand("guides", "Гайды для новичков"),
    BotCommand("ai", "Задать вопрос AI-агенту"),
    BotCommand("admin", "Панель администратора"),
    BotCommand("set_tag", "Назначить роль [admin]"),
    BotCommand("create_order", "Создать заказ [admin]"),
    BotCommand("add_guide", "Добавить гайд [admin]"),
    BotCommand("send_news", "Разослать новость [admin]"),
    BotCommand("balance_adjust", "Изменить баланс [admin]"),
    BotCommand("cancel", "Отменить текущее действие"),
]


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands set.")


def main() -> None:
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register all handlers (order matters for ConversationHandlers)
    for handler in [
        *build_registration_handlers(),
        *build_admin_handlers(),
        *build_report_handlers(),
        *build_balance_handlers(),
        *build_order_handlers(),
        *build_rating_handlers(),
        *build_calculator_handlers(),
        *build_guides_handlers(),
        *build_news_handlers(),
        *build_tag_handlers(),
        *build_ai_handlers(),
        CommandHandler("menu", menu),
    ]:
        app.add_handler(handler)

    logger.info("Starting Weeping Ghosts bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
