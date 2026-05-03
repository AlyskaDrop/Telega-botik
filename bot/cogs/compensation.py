"""
Cog: Compensation
Members submit ship-loss screenshots; admins review and approve payouts.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import GUILD_ID, ADMIN_ROLE_ID, LOG_CHANNEL_ID, COMPENSATION_RATE
from bot.database import get_db, get_balance, update_isk
from bot.utils.ocr import extract_ship_loss
from bot.utils.helpers import format_isk


def _is_admin(interaction: discord.Interaction) -> bool:
    if not ADMIN_ROLE_ID:
        return interaction.user.guild_permissions.administrator
    return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)


class Compensation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /compensation_claim ────────────────────────────────────────────────────
    @app_commands.command(
        name="compensation_claim",
        description="Запросить компенсацию за потерю корабля (прикрепи скриншот)",
    )
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def claim(self, interaction: discord.Interaction, screenshot: discord.Attachment) -> None:
        await interaction.response.defer(ephemeral=True)

        if not screenshot.content_type or not screenshot.content_type.startswith("image"):
            await interaction.followup.send("❌ Прикрепи скриншот потери корабля.", ephemeral=True)
            return

        data = await get_balance(interaction.user.id)
        if not data:
            await interaction.followup.send("❌ Сначала зарегистрируйся: /register", ephemeral=True)
            return

        parsed = await extract_ship_loss(screenshot.url)
        ship_name = parsed.get("ship_name", "")
        isk_value = parsed.get("isk_value", 0)
        system = parsed.get("system", "")

        if isk_value <= 0:
            await interaction.followup.send(
                "❌ Не удалось определить стоимость корабля. Убедись, что скриншот чёткий.", ephemeral=True
            )
            return

        payout = int(isk_value * COMPENSATION_RATE)

        async with await get_db() as db:
            cur = await db.execute(
                """INSERT INTO compensations (discord_id, ship_name, isk_value, payout_isk, screenshot)
                   VALUES (?,?,?,?,?)""",
                (interaction.user.id, ship_name, isk_value, payout, screenshot.url),
            )
            claim_id = cur.lastrowid
            await db.execute(
                "INSERT INTO screenshot_log (discord_id, purpose, url) VALUES (?,?,?)",
                (interaction.user.id, "compensation", screenshot.url),
            )
            await db.commit()

        embed = discord.Embed(title=f"📩 Заявка #{claim_id} подана", color=discord.Color.orange())
        embed.add_field(name="Корабль", value=ship_name or "—", inline=True)
        embed.add_field(name="Стоимость", value=format_isk(isk_value), inline=True)
        embed.add_field(name="Ожидаемая компенсация", value=format_isk(payout), inline=True)
        embed.add_field(name="Система", value=system or "—", inline=True)
        embed.set_footer(text=f"Коэффициент компенсации: {int(COMPENSATION_RATE*100)}%")
        embed.set_thumbnail(url=screenshot.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

        guild = interaction.guild
        if LOG_CHANNEL_ID and (log_ch := guild.get_channel(LOG_CHANNEL_ID)):
            log_embed = discord.Embed(
                title=f"🆕 Заявка на компенсацию #{claim_id}",
                description=f"{interaction.user.mention} потерял **{ship_name or '?'}** ({format_isk(isk_value)})\n"
                            f"Ожидаемая выплата: **{format_isk(payout)}**",
                color=discord.Color.orange(),
            )
            log_embed.set_thumbnail(url=screenshot.url)
            log_embed.set_footer(text=f"Одобрить: /compensation_approve {claim_id} | Отклонить: /compensation_reject {claim_id}")
            await log_ch.send(embed=log_embed)

    # ── /compensation_approve ──────────────────────────────────────────────────
    @app_commands.command(name="compensation_approve", description="[Админ] Одобрить заявку на компенсацию")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def approve(
        self, interaction: discord.Interaction, claim_id: int, override_isk: int | None = None
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        async with await get_db() as db:
            rows = await db.execute_fetchall(
                "SELECT * FROM compensations WHERE id=? AND status='pending'", (claim_id,)
            )
            if not rows:
                await interaction.response.send_message("❌ Заявка не найдена.", ephemeral=True)
                return
            claim = rows[0]
            payout = override_isk if override_isk is not None else claim["payout_isk"]
            await db.execute(
                """UPDATE compensations SET status='approved', payout_isk=?, reviewed_by=?,
                   updated_at=datetime('now') WHERE id=?""",
                (payout, interaction.user.id, claim_id),
            )
            await db.commit()

        await update_isk(
            claim["discord_id"], payout,
            note=f"Compensation #{claim_id}: {claim['ship_name']}",
            approved_by=interaction.user.id,
        )

        guild = interaction.guild
        if member := guild.get_member(claim["discord_id"]):
            try:
                dm_embed = discord.Embed(
                    title="✅ Компенсация одобрена",
                    description=f"Твоя заявка #{claim_id} одобрена. Зачислено **{format_isk(payout)}**.",
                    color=discord.Color.green(),
                )
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            f"✅ Заявка #{claim_id} одобрена. {format_isk(payout)} зачислено."
        )

    # ── /compensation_reject ───────────────────────────────────────────────────
    @app_commands.command(name="compensation_reject", description="[Админ] Отклонить заявку на компенсацию")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def reject(self, interaction: discord.Interaction, claim_id: int, reason: str = "") -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        async with await get_db() as db:
            rows = await db.execute_fetchall(
                "SELECT * FROM compensations WHERE id=? AND status='pending'", (claim_id,)
            )
            if not rows:
                await interaction.response.send_message("❌ Заявка не найдена.", ephemeral=True)
                return
            claim = rows[0]
            await db.execute(
                "UPDATE compensations SET status='rejected', reviewed_by=?, updated_at=datetime('now') WHERE id=?",
                (interaction.user.id, claim_id),
            )
            await db.commit()

        guild = interaction.guild
        if member := guild.get_member(claim["discord_id"]):
            try:
                await member.send(
                    f"❌ Твоя заявка на компенсацию #{claim_id} отклонена."
                    + (f" Причина: {reason}" if reason else "")
                )
            except discord.Forbidden:
                pass

        await interaction.response.send_message(f"✅ Заявка #{claim_id} отклонена.")

    # ── /compensation_list ─────────────────────────────────────────────────────
    @app_commands.command(name="compensation_list", description="[Админ] Список заявок на компенсацию")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def comp_list(self, interaction: discord.Interaction, status: str = "pending") -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        async with await get_db() as db:
            rows = await db.execute_fetchall(
                "SELECT * FROM compensations WHERE status=? ORDER BY created_at DESC LIMIT 20",
                (status,),
            )

        if not rows:
            await interaction.response.send_message(f"📭 Заявок со статусом «{status}» нет.", ephemeral=True)
            return

        lines = [
            f"**#{r['id']}** <@{r['discord_id']}> — {r['ship_name'] or '?'} "
            f"({format_isk(r['isk_value'])}) → {format_isk(r['payout_isk'])}"
            for r in rows
        ]
        embed = discord.Embed(
            title=f"📋 Компенсации ({status})",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Compensation(bot))
