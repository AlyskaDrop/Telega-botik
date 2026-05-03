"""
Cog: Admin Panel
Grant/revoke ISK, points, roles; view all member data.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import GUILD_ID, ADMIN_ROLE_ID, LOG_CHANNEL_ID
from bot.database import get_db, get_balance, update_isk, update_points, get_or_create_member
from bot.utils.helpers import format_isk


def _is_admin(interaction: discord.Interaction) -> bool:
    if not ADMIN_ROLE_ID:
        return interaction.user.guild_permissions.administrator
    return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /admin_grant_isk ───────────────────────────────────────────────────────
    @app_commands.command(name="admin_grant_isk", description="[Админ] Начислить ISK участнику")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def grant_isk(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
        reason: str = "",
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        data = await get_balance(member.id)
        if not data:
            await interaction.response.send_message("❌ Участник не зарегистрирован.", ephemeral=True)
            return
        new_bal = await update_isk(member.id, amount, note=reason or "admin grant", approved_by=interaction.user.id)
        await interaction.response.send_message(
            f"✅ {format_isk(amount)} начислено {member.mention}. Новый баланс: {format_isk(new_bal)}"
        )
        await self._log(interaction, f"💰 Начислено {format_isk(amount)} → {member.mention} | Причина: {reason or '—'}")

    # ── /admin_deduct_isk ──────────────────────────────────────────────────────
    @app_commands.command(name="admin_deduct_isk", description="[Админ] Списать ISK с участника")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def deduct_isk(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
        reason: str = "",
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        new_bal = await update_isk(member.id, -amount, note=reason or "admin deduct", approved_by=interaction.user.id)
        await interaction.response.send_message(
            f"✅ {format_isk(amount)} списано с {member.mention}. Новый баланс: {format_isk(new_bal)}"
        )
        await self._log(interaction, f"➖ Списано {format_isk(amount)} ← {member.mention} | Причина: {reason or '—'}")

    # ── /admin_grant_points ────────────────────────────────────────────────────
    @app_commands.command(name="admin_grant_points", description="[Админ] Начислить очки участнику")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def grant_points(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        pvp: int = 0,
        pve: int = 0,
        reason: str = "",
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        new_pvp, new_pve = await update_points(member.id, pvp=pvp, pve=pve, note=reason or "admin grant")
        await interaction.response.send_message(
            f"✅ +{pvp} PvP / +{pve} PvE → {member.mention}. Итого: {new_pvp} / {new_pve}"
        )

    # ── /admin_deduct_points ───────────────────────────────────────────────────
    @app_commands.command(name="admin_deduct_points", description="[Админ] Списать очки у участника")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def deduct_points(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        pvp: int = 0,
        pve: int = 0,
        reason: str = "",
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        new_pvp, new_pve = await update_points(member.id, pvp=-pvp, pve=-pve, note=reason or "admin deduct")
        await interaction.response.send_message(
            f"✅ -{pvp} PvP / -{pve} PvE ← {member.mention}. Итого: {new_pvp} / {new_pve}"
        )

    # ── /admin_grant_role ──────────────────────────────────────────────────────
    @app_commands.command(name="admin_grant_role", description="[Админ] Выдать роль участнику")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def grant_role(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        await member.add_roles(role, reason=f"Admin: {interaction.user}")
        await interaction.response.send_message(f"✅ Роль {role.mention} выдана {member.mention}.")
        await self._log(interaction, f"🎖️ Роль {role.name} выдана {member.mention}")

    # ── /admin_revoke_role ─────────────────────────────────────────────────────
    @app_commands.command(name="admin_revoke_role", description="[Админ] Снять роль с участника")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def revoke_role(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        await member.remove_roles(role, reason=f"Admin: {interaction.user}")
        await interaction.response.send_message(f"✅ Роль {role.mention} снята с {member.mention}.")
        await self._log(interaction, f"🚫 Роль {role.name} снята с {member.mention}")

    # ── /admin_members ─────────────────────────────────────────────────────────
    @app_commands.command(name="admin_members", description="[Админ] Список всех зарегистрированных участников")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def admin_members(self, interaction: discord.Interaction, page: int = 1) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        per_page = 15
        offset = (max(page, 1) - 1) * per_page
        async with await get_db() as db:
            rows = await db.execute_fetchall(
                """SELECT m.discord_id, m.pilot_name, m.is_verified, b.isk_balance,
                          b.pvp_points, b.pve_points
                   FROM members m LEFT JOIN balances b USING (discord_id)
                   ORDER BY m.joined_at DESC LIMIT ? OFFSET ?""",
                (per_page, offset),
            )
            total_row = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM members")

        total = total_row[0]["cnt"] if total_row else 0
        total_pages = max(1, (total + per_page - 1) // per_page)

        lines = [
            f"{'✅' if r['is_verified'] else '❌'} <@{r['discord_id']}> **{r['pilot_name']}** "
            f"| {format_isk(r['isk_balance'] or 0)} | ⚔️{r['pvp_points'] or 0} 🐉{r['pve_points'] or 0}"
            for r in rows
        ]
        embed = discord.Embed(
            title=f"👥 Участники (стр. {page}/{total_pages}, всего {total})",
            description="\n".join(lines) or "—",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /admin_verify ──────────────────────────────────────────────────────────
    @app_commands.command(name="admin_verify", description="[Админ] Верифицировать участника вручную")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def admin_verify(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        pilot_name: str,
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        await get_or_create_member(member.id, pilot_name)
        async with await get_db() as db:
            await db.execute(
                "UPDATE members SET is_verified=1, pilot_name=? WHERE discord_id=?",
                (pilot_name, member.id),
            )
            await db.commit()
        await interaction.response.send_message(
            f"✅ {member.mention} верифицирован как **{pilot_name}**."
        )

    # ── Internal log helper ────────────────────────────────────────────────────
    async def _log(self, interaction: discord.Interaction, message: str) -> None:
        if LOG_CHANNEL_ID and (log_ch := interaction.guild.get_channel(LOG_CHANNEL_ID)):
            embed = discord.Embed(
                description=message,
                color=discord.Color.dark_gray(),
            )
            embed.set_footer(text=f"Админ: {interaction.user}")
            await log_ch.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
