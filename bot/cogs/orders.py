"""
Cog: Orders
Corporate mission board – admins post orders, members accept and complete them.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import GUILD_ID, ADMIN_ROLE_ID, LOG_CHANNEL_ID
from bot.database import get_db, get_balance, update_isk
from bot.utils.helpers import format_isk, paginate


def _is_admin(interaction: discord.Interaction) -> bool:
    if not ADMIN_ROLE_ID:
        return interaction.user.guild_permissions.administrator
    return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)


class Orders(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /order_add ─────────────────────────────────────────────────────────────
    @app_commands.command(name="order_add", description="[Админ] Добавить корпоративный заказ")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def order_add(
        self,
        interaction: discord.Interaction,
        title: str,
        reward_isk: int,
        description: str = "",
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        async with await get_db() as db:
            cur = await db.execute(
                "INSERT INTO orders (title, description, reward_isk, created_by) VALUES (?,?,?,?)",
                (title, description, reward_isk, interaction.user.id),
            )
            order_id = cur.lastrowid
            await db.commit()

        embed = discord.Embed(title=f"📋 Заказ #{order_id} создан", color=discord.Color.green())
        embed.add_field(name="Название", value=title, inline=False)
        embed.add_field(name="Награда", value=format_isk(reward_isk), inline=True)
        if description:
            embed.add_field(name="Описание", value=description, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /orders ────────────────────────────────────────────────────────────────
    @app_commands.command(name="orders", description="Список открытых заказов корпорации")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def orders_list(self, interaction: discord.Interaction, page: int = 1) -> None:
        async with await get_db() as db:
            rows = await db.execute_fetchall(
                "SELECT * FROM orders WHERE status='open' ORDER BY created_at DESC"
            )

        if not rows:
            await interaction.response.send_message("📭 Открытых заказов нет.", ephemeral=True)
            return

        items, total_pages = paginate(list(rows), page)
        lines = [
            f"**#{r['id']}** {r['title']} — {format_isk(r['reward_isk'])}"
            + (f"\n> {r['description']}" if r["description"] else "")
            for r in items
        ]
        embed = discord.Embed(
            title=f"📋 Заказы корпорации (стр. {page}/{total_pages})",
            description="\n\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed)

    # ── /order_take ────────────────────────────────────────────────────────────
    @app_commands.command(name="order_take", description="Взять заказ на выполнение")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def order_take(self, interaction: discord.Interaction, order_id: int) -> None:
        data = await get_balance(interaction.user.id)
        if not data:
            await interaction.response.send_message("❌ Сначала зарегистрируйся: /register", ephemeral=True)
            return

        async with await get_db() as db:
            rows = await db.execute_fetchall(
                "SELECT * FROM orders WHERE id=? AND status='open'", (order_id,)
            )
            if not rows:
                await interaction.response.send_message("❌ Заказ не найден или уже занят.", ephemeral=True)
                return
            await db.execute(
                "UPDATE orders SET assigned_to=?, status='assigned', updated_at=datetime('now') WHERE id=?",
                (interaction.user.id, order_id),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Ты взял заказ **#{order_id}** «{rows[0]['title']}». По завершении используй `/order_complete {order_id}`."
        )

    # ── /order_complete ────────────────────────────────────────────────────────
    @app_commands.command(name="order_complete", description="Отметить заказ выполненным (требует одобрения)")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def order_complete(self, interaction: discord.Interaction, order_id: int) -> None:
        async with await get_db() as db:
            rows = await db.execute_fetchall(
                "SELECT * FROM orders WHERE id=? AND assigned_to=? AND status='assigned'",
                (order_id, interaction.user.id),
            )
            if not rows:
                await interaction.response.send_message("❌ Заказ не найден или не назначен тебе.", ephemeral=True)
                return
            await db.execute(
                "UPDATE orders SET status='pending_review', updated_at=datetime('now') WHERE id=?",
                (order_id,),
            )
            await db.commit()

        guild = interaction.guild
        if LOG_CHANNEL_ID and (log_ch := guild.get_channel(LOG_CHANNEL_ID)):
            await log_ch.send(
                f"📝 {interaction.user.mention} отмечает заказ **#{order_id}** «{rows[0]['title']}» как выполненный. "
                f"Требуется одобрение админа: `/order_approve {order_id}`"
            )
        await interaction.response.send_message(
            f"✅ Заказ #{order_id} отправлен на проверку.", ephemeral=True
        )

    # ── /order_approve ─────────────────────────────────────────────────────────
    @app_commands.command(name="order_approve", description="[Админ] Одобрить выполнение заказа")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def order_approve(self, interaction: discord.Interaction, order_id: int) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        async with await get_db() as db:
            rows = await db.execute_fetchall(
                "SELECT * FROM orders WHERE id=? AND status='pending_review'", (order_id,)
            )
            if not rows:
                await interaction.response.send_message("❌ Заказ не найден или не ожидает одобрения.", ephemeral=True)
                return
            order = rows[0]
            await db.execute(
                "UPDATE orders SET status='completed', updated_at=datetime('now') WHERE id=?",
                (order_id,),
            )
            await db.commit()

        await update_isk(
            order["assigned_to"],
            order["reward_isk"],
            note=f"Order #{order_id} reward",
            approved_by=interaction.user.id,
        )
        await interaction.response.send_message(
            f"✅ Заказ #{order_id} одобрен. {format_isk(order['reward_isk'])} зачислено исполнителю."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Orders(bot))
