"""
Cog: Auto Roles
Automatically assign reward roles based on ISK balance / points milestones.
Runs a background task every 10 minutes and also triggers on balance updates.
"""

from __future__ import annotations

import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.config import GUILD_ID, REWARD_ROLES
from bot.database import get_db


class AutoRoles(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._lock = asyncio.Lock()

    # Start background loop after cog is ready
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self.auto_role_loop.is_running():
            self.auto_role_loop.start()

    def cog_unload(self) -> None:
        self.auto_role_loop.cancel()

    @tasks.loop(minutes=10)
    async def auto_role_loop(self) -> None:
        await self.run_auto_roles()

    @auto_role_loop.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def run_auto_roles(self) -> None:
        if not REWARD_ROLES:
            return

        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        async with self._lock:
            async with await get_db() as db:
                rows = await db.execute_fetchall(
                    "SELECT m.discord_id, b.isk_balance FROM members m JOIN balances b USING (discord_id)"
                )

            for row in rows:
                member = guild.get_member(row["discord_id"])
                if not member:
                    continue

                isk = row["isk_balance"]
                for threshold_isk, role_id in sorted(REWARD_ROLES.items()):
                    role = guild.get_role(role_id)
                    if not role:
                        continue
                    if isk >= threshold_isk and role not in member.roles:
                        try:
                            await member.add_roles(role, reason="Auto-reward: ISK milestone")
                        except discord.Forbidden:
                            pass
                    elif isk < threshold_isk and role in member.roles:
                        try:
                            await member.remove_roles(role, reason="Auto-reward: ISK below threshold")
                        except discord.Forbidden:
                            pass

    # ── /sync_roles ────────────────────────────────────────────────────────────
    @app_commands.command(name="sync_roles", description="[Админ] Принудительно синхронизировать роли-награды")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def sync_roles(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await self.run_auto_roles()
        await interaction.followup.send("✅ Роли синхронизированы.", ephemeral=True)

    # ── /reward_roles ──────────────────────────────────────────────────────────
    @app_commands.command(name="reward_roles", description="Список пороговых значений для автоматических ролей")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def reward_roles_info(self, interaction: discord.Interaction) -> None:
        if not REWARD_ROLES:
            await interaction.response.send_message(
                "ℹ️ Автоматические роли-награды не настроены. Задай `REWARD_ROLES` в `.env`.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        lines = []
        for threshold, role_id in sorted(REWARD_ROLES.items()):
            role = guild.get_role(role_id)
            role_str = role.mention if role else f"(id:{role_id})"
            from bot.utils.helpers import format_isk
            lines.append(f"{role_str} — порог: **{format_isk(threshold)}**")

        embed = discord.Embed(
            title="🎖️ Роли-награды (ISK порог)",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoRoles(bot))
