"""
Cog: Registration
Players attach an Eve Echoes character-info screenshot to register.
Bot extracts pilot name, verifies corp membership, assigns MEMBER_ROLE.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import aiosqlite
from bot.config import GUILD_ID, MEMBER_ROLE_ID, VERIFIED_ROLE_ID, LOG_CHANNEL_ID
from bot.database import get_db, get_or_create_member
from bot.utils.ocr import extract_registration


class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /register ─────────────────────────────────────────────────────────────
    @app_commands.command(name="register", description="Зарегистрироваться в корпорации (приложи скриншот)")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def register(self, interaction: discord.Interaction, screenshot: discord.Attachment) -> None:
        await interaction.response.defer(ephemeral=True)

        if not screenshot.content_type or not screenshot.content_type.startswith("image"):
            await interaction.followup.send("❌ Прикрепи изображение (скриншот из Eve Echoes).", ephemeral=True)
            return

        data = await extract_registration(screenshot.url)
        pilot_name = data.get("pilot_name", "").strip()
        corporation = data.get("corporation", "").strip()

        if not pilot_name:
            await interaction.followup.send(
                "❌ Не удалось распознать имя пилота. Убедись, что скриншот чёткий.", ephemeral=True
            )
            return

        await get_or_create_member(interaction.user.id, pilot_name)

        # Mark verified and assign role
        async with await get_db() as db:
            await db.execute(
                "UPDATE members SET is_verified=1, pilot_name=? WHERE discord_id=?",
                (pilot_name, interaction.user.id),
            )
            await db.execute(
                """INSERT OR IGNORE INTO screenshot_log (discord_id, purpose, url)
                   VALUES (?, 'registration', ?)""",
                (interaction.user.id, screenshot.url),
            )
            await db.commit()

        guild = interaction.guild
        member = interaction.user

        roles_to_add = []
        if MEMBER_ROLE_ID and (role := guild.get_role(MEMBER_ROLE_ID)):
            roles_to_add.append(role)
        if VERIFIED_ROLE_ID and (role := guild.get_role(VERIFIED_ROLE_ID)):
            roles_to_add.append(role)

        if roles_to_add and isinstance(member, discord.Member):
            await member.add_roles(*roles_to_add, reason="Auto-registration")

        embed = discord.Embed(
            title="✅ Регистрация успешна!",
            color=discord.Color.green(),
        )
        embed.add_field(name="Пилот", value=pilot_name, inline=True)
        embed.add_field(name="Корпорация", value=corporation or "—", inline=True)
        embed.set_thumbnail(url=screenshot.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Log
        if LOG_CHANNEL_ID and (log_ch := guild.get_channel(LOG_CHANNEL_ID)):
            log_embed = discord.Embed(
                title="📋 Новая регистрация",
                description=f"{member.mention} зарегистрировался как **{pilot_name}**",
                color=discord.Color.blue(),
            )
            log_embed.set_thumbnail(url=screenshot.url)
            await log_ch.send(embed=log_embed)

    # ── /whois ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="whois", description="Посмотреть данные участника")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def whois(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        target = member or interaction.user
        async with await get_db() as db:
            rows = await db.execute_fetchall(
                "SELECT * FROM members WHERE discord_id=?", (target.id,)
            )
        if not rows:
            await interaction.response.send_message("❌ Участник не зарегистрирован.", ephemeral=True)
            return
        row = rows[0]
        embed = discord.Embed(title=f"👤 {row['pilot_name']}", color=discord.Color.blurple())
        embed.add_field(name="Discord", value=target.mention)
        embed.add_field(name="Верифицирован", value="✅" if row["is_verified"] else "❌")
        embed.add_field(name="Дата регистрации", value=row["joined_at"][:10])
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Registration(bot))
