"""AI agent: answer questions about Eve Echoes using OpenAI."""

from __future__ import annotations

from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

from config import OPENAI_API_KEY, OPENAI_MODEL

SYSTEM_PROMPT = (
    "Ты — помощник корпорации Weeping Ghosts в игре Eve Echoes. "
    "Отвечай на русском языке, кратко и по существу. "
    "Помогай с вопросами об игровой механике, фиттинге кораблей, PvP и PvE тактиках, "
    "промышленности, маршрутах и корпоративной жизни. "
    "Если вопрос не касается игры или корпорации — вежливо перенаправь."
)


async def ai_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not OPENAI_API_KEY:
        await update.message.reply_text(
            "⚠️ AI-агент временно недоступен (не настроен API ключ)."
        )
        return

    user_text = " ".join(context.args) if context.args else ""
    if not user_text:
        await update.message.reply_text(
            "Использование: /ai <вопрос>\nНапример: /ai Какой лучший фит для PvP в нулях?"
        )
        return

    await update.message.reply_text("🤖 Думаю...")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            max_tokens=800,
            temperature=0.7,
        )
        answer = response.choices[0].message.content or "Не удалось получить ответ."
    except Exception as e:
        answer = f"❌ Ошибка AI-агента: {e}"

    await update.message.reply_text(f"🤖 *AI-агент:*\n{answer}", parse_mode="Markdown")


async def ai_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages starting with '?' as quick AI questions in any chat."""
    text = update.message.text
    if not text or not text.startswith("?"):
        return

    question = text[1:].strip()
    if not question:
        return

    context.args = question.split()
    await ai_ask(update, context)


def build_ai_handlers() -> list:
    return [
        CommandHandler("ai", ai_ask),
        MessageHandler(filters.TEXT & filters.Regex(r"^\?"), ai_inline),
    ]
