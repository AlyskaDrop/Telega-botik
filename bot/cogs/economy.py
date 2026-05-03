"""
Cog: Economy
ISK balance crediting via screenshot + balance/transaction queries.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import GUILD_ID, LOG_CHANNEL_ID
from bot.database import get_db, get_or_create_member, get_balance, update_isk
from bot.utils.ocr import extract_isk
from bot.utils.helpers import format_isk


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /balance ───────────────────────────────────────────────────────────────
    @app_commands.command(name="balance", description="Проверить баланс ISK и очки")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def balance(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        target = member or interaction.user
        data = await get_balance(target.id)
        if not data:
            await interaction.response.send_message("❌ Участник не зарегистрирован.", ephemeral=True)
            return
        embed = discord.Embed(title=f"💰 Баланс — {data['pilot_name']}", color=discord.Color.gold())
        embed.add_field(name="ISK", value=format_isk(data["isk_balance"]), inline=True)
        embed.add_field(name="PvP очки", value=str(data["pvp_points"]), inline=True)
        embed.add_field(name="PvE очки", value=str(data["pve_points"]), inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /deposit ───────────────────────────────────────────────────────────────
    @app_commands.command(name="deposit", description="Зачислить ISK по скриншоту")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def deposit(self, interaction: discord.Interaction, screenshot: discord.Attachment) -> None:
        await interaction.response.defer(ephemeral=True)

        if not screenshot.content_type or not screenshot.content_type.startswith("image"):
            await interaction.followup.send("❌ Прикрепи скриншот.", ephemeral=True)
            return

        # Ensure member exists
        data = await get_balance(interaction.user.id)
        if not data:
            await interaction.followup.send("❌ Сначала зарегистрируйся командой /register.", ephemeral=True)
            return

        parsed = await extract_isk(screenshot.url)
        amount = parsed.get("isk_amount", 0)
        description = parsed.get("description", "")

        if amount <= 0:
            await interaction.followup.send(
                "❌ Не удалось определить сумму ISK. Убедись, что скриншот чёткий.", ephemeral=True
            )
            return

        # Log screenshot
        async with await get_db() as db:
            await db.execute(
                "INSERT INTO screenshot_log (discord_id, purpose, url) VALUES (?,?,?)",
                (interaction.user.id, "isk_deposit", screenshot.url),
            )
            await db.commit()

        new_balance = await update_isk(
            interaction.user.id, amount, note=description or "deposit via screenshot"
        )

        embed = discord.Embed(title="✅ ISK зачислен", color=discord.Color.green())
        embed.add_field(name="Зачислено", value=format_isk(amount), inline=True)
        embed.add_field(name="Новый баланс", value=format_isk(new_balance), inline=True)
        if description:
            embed.add_field(name="Описание", value=description, inline=False)
        embed.set_thumbnail(url=screenshot.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Admin log
        guild = interaction.guild
        if LOG_CHANNEL_ID and (log_ch := guild.get_channel(LOG_CHANNEL_ID)):
            log_embed = discord.Embed(
                title="💵 Зачисление ISK",
                description=f"{interaction.user.mention} зачислил {format_isk(amount)}",
                color=discord.Color.yellow(),
            )
            log_embed.set_thumbnail(url=screenshot.url)
            await log_ch.send(embed=log_embed)

    # ── /transactions ──────────────────────────────────────────────────────────
    @app_commands.command(name="transactions", description="История транзакций")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def transactions(
        self, interaction: discord.Interaction, member: discord.Member | None = None, page: int = 1
    ) -> None:
        target = member or interaction.user
        per_page = 10
        offset = (max(page, 1) - 1) * per_page

        async with await get_db() as db:
            rows = await db.execute_fetchall(
                """SELECT type, amount, note, created_at FROM transactions
                   WHERE discord_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (target.id, per_page, offset),
            )

        if not rows:
            await interaction.response.send_message("📭 Транзакции не найдены.", ephemeral=True)
            return

        lines = [
            f"`{r['created_at'][:10]}` **{r['type']}** {format_isk(r['amount'])} — {r['note'] or '—'}"
            for r in rows
        ]
        embed = discord.Embed(
            title=f"📋 Транзакции — {target.display_name} (стр. {page})",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
