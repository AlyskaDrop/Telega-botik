"""
Cog: Points
Count PvP and PvE points from kill-mail / combat-log screenshots.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import GUILD_ID, LOG_CHANNEL_ID
from bot.database import get_db, get_balance, update_points
from bot.utils.ocr import extract_kill
from bot.utils.helpers import format_isk


# ISK→point conversion: every 1 M ISK destroyed = 1 PvP point
ISK_PER_POINT = 1_000_000


class Points(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /kill_submit ───────────────────────────────────────────────────────────
    @app_commands.command(name="kill_submit", description="Отправить скриншот убийства/активности для начисления очков")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def kill_submit(
        self,
        interaction: discord.Interaction,
        screenshot: discord.Attachment,
        kill_type: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not screenshot.content_type or not screenshot.content_type.startswith("image"):
            await interaction.followup.send("❌ Прикрепи изображение.", ephemeral=True)
            return

        data = await get_balance(interaction.user.id)
        if not data:
            await interaction.followup.send("❌ Сначала зарегистрируйся: /register", ephemeral=True)
            return

        parsed = await extract_kill(screenshot.url)
        kill_type = parsed.get("kill_type", "pvp").lower()
        isk_value = parsed.get("isk_value", 0)
        pilot_name = parsed.get("pilot_name", data["pilot_name"])
        ship_name = parsed.get("ship_name", "")
        victim_name = parsed.get("victim_name", "")
        victim_ship = parsed.get("victim_ship", "")
        system = parsed.get("system", "")

        points = max(1, isk_value // ISK_PER_POINT)

        async with await get_db() as db:
            await db.execute(
                """INSERT INTO kills
                   (discord_id, pilot_name, ship_name, victim_name, victim_ship,
                    system, isk_value, kill_type, screenshot)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (interaction.user.id, pilot_name, ship_name, victim_name,
                 victim_ship, system, isk_value, kill_type, screenshot.url),
            )
            await db.execute(
                "INSERT INTO screenshot_log (discord_id, purpose, url) VALUES (?,?,?)",
                (interaction.user.id, f"kill_{kill_type}", screenshot.url),
            )
            await db.commit()

        if kill_type == "pvp":
            new_pvp, _ = await update_points(interaction.user.id, pvp=points, note=f"kill {system}")
            points_label, new_label = "PvP очки", str(new_pvp)
        else:
            _, new_pve = await update_points(interaction.user.id, pve=points, note=f"pve {system}")
            points_label, new_label = "PvE очки", str(new_pve)

        embed = discord.Embed(
            title=f"⚔️ Килл засчитан ({'PvP' if kill_type == 'pvp' else 'PvE'})",
            color=discord.Color.red() if kill_type == "pvp" else discord.Color.orange(),
        )
        embed.add_field(name="Пилот", value=pilot_name or "—", inline=True)
        embed.add_field(name="Корабль", value=ship_name or "—", inline=True)
        embed.add_field(name="Жертва", value=victim_name or "—", inline=True)
        embed.add_field(name="Система", value=system or "—", inline=True)
        embed.add_field(name="ISK уничтожено", value=format_isk(isk_value), inline=True)
        embed.add_field(name=f"+{points_label}", value=f"+{points} → {new_label}", inline=True)
        embed.set_thumbnail(url=screenshot.url)
        await interaction.followup.send(embed=embed, ephemeral=False)

        # Post to killboard channel
        guild = interaction.guild
        from bot.config import KILLBOARD_CHANNEL_ID
        if KILLBOARD_CHANNEL_ID and (kb_ch := guild.get_channel(KILLBOARD_CHANNEL_ID)):
            await kb_ch.send(embed=embed)

    # ── /points ────────────────────────────────────────────────────────────────
    @app_commands.command(name="points", description="Посмотреть очки участника")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def points_cmd(
        self, interaction: discord.Interaction, member: discord.Member | None = None
    ) -> None:
        target = member or interaction.user
        data = await get_balance(target.id)
        if not data:
            await interaction.response.send_message("❌ Участник не зарегистрирован.", ephemeral=True)
            return
        embed = discord.Embed(title=f"🏆 Очки — {data['pilot_name']}", color=discord.Color.gold())
        embed.add_field(name="PvP", value=str(data["pvp_points"]), inline=True)
        embed.add_field(name="PvE", value=str(data["pve_points"]), inline=True)
        embed.add_field(name="Всего", value=str(data["pvp_points"] + data["pve_points"]), inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /leaderboard ───────────────────────────────────────────────────────────
    @app_commands.command(name="leaderboard", description="Таблица лидеров по очкам")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        async with await get_db() as db:
            rows = await db.execute_fetchall(
                """SELECT m.pilot_name, b.pvp_points, b.pve_points,
                          (b.pvp_points + b.pve_points) AS total
                   FROM members m JOIN balances b USING (discord_id)
                   ORDER BY total DESC LIMIT 15"""
            )
        if not rows:
            await interaction.response.send_message("📭 Пока нет данных.", ephemeral=True)
            return

        lines = [
            f"**{i+1}.** {r['pilot_name']} — ⚔️{r['pvp_points']} 🐉{r['pve_points']} (∑{r['total']})"
            for i, r in enumerate(rows)
        ]
        embed = discord.Embed(
            title="🏆 Таблица лидеров",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Points(bot))
