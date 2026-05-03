"""
Cog: Killboard
Public kill feed + personal kill stats.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import GUILD_ID
from bot.database import get_db, get_balance
from bot.utils.helpers import format_isk, paginate


class Killboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /killboard ─────────────────────────────────────────────────────────────
    @app_commands.command(name="killboard", description="Таблица убийств корпорации")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def killboard(
        self,
        interaction: discord.Interaction,
        kill_type: str | None = None,   # pvp / pve / loss / all
        page: int = 1,
    ) -> None:
        kill_type = (kill_type or "pvp").lower()

        async with await get_db() as db:
            if kill_type == "all":
                rows = await db.execute_fetchall(
                    "SELECT * FROM kills ORDER BY created_at DESC"
                )
            else:
                rows = await db.execute_fetchall(
                    "SELECT * FROM kills WHERE kill_type=? ORDER BY created_at DESC",
                    (kill_type,),
                )

        if not rows:
            await interaction.response.send_message("📭 Нет записей.", ephemeral=True)
            return

        items, total_pages = paginate(list(rows), page)

        lines = []
        for r in items:
            icon = "⚔️" if r["kill_type"] == "pvp" else ("🐉" if r["kill_type"] == "pve" else "💀")
            line = (
                f"{icon} **{r['pilot_name']}** [{r['ship_name'] or '?'}]"
                f" vs {r['victim_name'] or '?'} [{r['victim_ship'] or '?'}]"
                f" — {format_isk(r['isk_value'])} | {r['system'] or '?'}"
                f" `{r['created_at'][:10]}`"
            )
            lines.append(line)

        embed = discord.Embed(
            title=f"☠️ Killboard — {kill_type.upper()} (стр. {page}/{total_pages})",
            description="\n".join(lines),
            color=discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed)

    # ── /kills ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="kills", description="Личная статистика убийств")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def kills(
        self, interaction: discord.Interaction, member: discord.Member | None = None
    ) -> None:
        target = member or interaction.user
        data = await get_balance(target.id)
        if not data:
            await interaction.response.send_message("❌ Участник не зарегистрирован.", ephemeral=True)
            return

        async with await get_db() as db:
            stats = await db.execute_fetchall(
                """SELECT kill_type, COUNT(*) AS cnt, SUM(isk_value) AS total_isk
                   FROM kills WHERE discord_id=? GROUP BY kill_type""",
                (target.id,),
            )
            recent = await db.execute_fetchall(
                """SELECT * FROM kills WHERE discord_id=? ORDER BY created_at DESC LIMIT 5""",
                (target.id,),
            )

        embed = discord.Embed(
            title=f"☠️ Статистика — {data['pilot_name']}",
            color=discord.Color.dark_red(),
        )

        for s in stats:
            embed.add_field(
                name=s["kill_type"].upper(),
                value=f"{s['cnt']} килл(ов) / {format_isk(s['total_isk'] or 0)}",
                inline=True,
            )

        if recent:
            recent_lines = [
                f"⚔️ {r['victim_name'] or '?'} [{r['victim_ship'] or '?'}] — {format_isk(r['isk_value'])}"
                for r in recent
            ]
            embed.add_field(name="Последние 5", value="\n".join(recent_lines), inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Killboard(bot))
