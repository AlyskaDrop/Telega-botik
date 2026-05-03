"""
Cog: AI Agent
Conversational assistant powered by GPT-4o; knows Eve Echoes context.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import GUILD_ID, OPENAI_API_KEY, OPENAI_MODEL

SYSTEM_PROMPT = """
Ты — ИИ-ассистент корпорации «Weeping Ghosts» в игре Eve Echoes (мобильная MMO).
Помогай участникам по вопросам игры: механики, корабли, импланты, добыча, производство, торговля, PvP/PvE.
Отвечай по-русски, кратко и конкретно. Если не знаешь ответа — честно скажи об этом.
"""

# Simple per-user conversation history (max 10 turns to save tokens)
_history: dict[int, list[dict]] = {}
MAX_HISTORY = 10


class AIAgent(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /ask ───────────────────────────────────────────────────────────────────
    @app_commands.command(name="ask", description="Спросить ИИ-агента о Eve Echoes")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def ask(self, interaction: discord.Interaction, question: str) -> None:
        await interaction.response.defer()

        if not OPENAI_API_KEY:
            await interaction.followup.send("❌ OpenAI API не настроен. Обратитесь к администратору.")
            return

        import openai
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

        uid = interaction.user.id
        history = _history.setdefault(uid, [])
        history.append({"role": "user", "content": question})

        # Trim history
        if len(history) > MAX_HISTORY * 2:
            _history[uid] = history[-(MAX_HISTORY * 2):]
            history = _history[uid]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        try:
            resp = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_tokens=1000,
            )
            answer = resp.choices[0].message.content or "Нет ответа."
            history.append({"role": "assistant", "content": answer})
        except Exception as exc:
            answer = f"❌ Ошибка: {exc}"

        embed = discord.Embed(color=discord.Color.blurple())
        embed.add_field(name="❓ Вопрос", value=question[:1000], inline=False)
        embed.add_field(name="🤖 Ответ", value=answer[:1000], inline=False)
        embed.set_footer(text=f"Модель: {OPENAI_MODEL} | /ask_clear — очистить историю")
        await interaction.followup.send(embed=embed)

    # ── /ask_clear ─────────────────────────────────────────────────────────────
    @app_commands.command(name="ask_clear", description="Очистить историю диалога с ИИ-агентом")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def ask_clear(self, interaction: discord.Interaction) -> None:
        _history.pop(interaction.user.id, None)
        await interaction.response.send_message("🗑️ История диалога очищена.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AIAgent(bot))
