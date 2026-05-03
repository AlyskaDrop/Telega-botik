"""
Cog: Goods / Corp Shop
Admins list items for sale; members buy with ISK balance.
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


class Goods(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /goods ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="goods", description="Товары корпорации")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def goods_list(self, interaction: discord.Interaction, page: int = 1) -> None:
        async with await get_db() as db:
            rows = await db.execute_fetchall(
                "SELECT * FROM goods WHERE stock > 0 ORDER BY name"
            )

        if not rows:
            await interaction.response.send_message("📭 Товаров нет.", ephemeral=True)
            return

        items, total_pages = paginate(list(rows), page)
        lines = [
            f"**#{r['id']}** {r['name']} — {format_isk(r['price_isk'])} (в наличии: {r['stock']})"
            + (f"\n> {r['description']}" if r["description"] else "")
            for r in items
        ]
        embed = discord.Embed(
            title=f"🛒 Магазин корпорации (стр. {page}/{total_pages})",
            description="\n\n".join(lines),
            color=discord.Color.green(),
        )
        embed.set_footer(text="Купить: /buy <id> [кол-во]")
        await interaction.response.send_message(embed=embed)

    # ── /good_add ──────────────────────────────────────────────────────────────
    @app_commands.command(name="good_add", description="[Админ] Добавить товар в магазин")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def good_add(
        self,
        interaction: discord.Interaction,
        name: str,
        price_isk: int,
        stock: int,
        description: str = "",
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        async with await get_db() as db:
            cur = await db.execute(
                "INSERT INTO goods (name, description, price_isk, stock, added_by) VALUES (?,?,?,?,?)",
                (name, description, price_isk, stock, interaction.user.id),
            )
            good_id = cur.lastrowid
            await db.commit()

        embed = discord.Embed(title=f"✅ Товар #{good_id} добавлен", color=discord.Color.green())
        embed.add_field(name="Название", value=name, inline=True)
        embed.add_field(name="Цена", value=format_isk(price_isk), inline=True)
        embed.add_field(name="Количество", value=str(stock), inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /good_restock ──────────────────────────────────────────────────────────
    @app_commands.command(name="good_restock", description="[Админ] Пополнить склад товара")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def good_restock(self, interaction: discord.Interaction, good_id: int, amount: int) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        async with await get_db() as db:
            rows = await db.execute_fetchall("SELECT * FROM goods WHERE id=?", (good_id,))
            if not rows:
                await interaction.response.send_message("❌ Товар не найден.", ephemeral=True)
                return
            await db.execute("UPDATE goods SET stock = stock + ? WHERE id=?", (amount, good_id))
            await db.commit()

        await interaction.response.send_message(f"✅ Добавлено {amount} ед. товара «{rows[0]['name']}».")

    # ── /buy ───────────────────────────────────────────────────────────────────
    @app_commands.command(name="buy", description="Купить товар корпорации")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def buy(self, interaction: discord.Interaction, good_id: int, quantity: int = 1) -> None:
        await interaction.response.defer(ephemeral=True)

        balance_data = await get_balance(interaction.user.id)
        if not balance_data:
            await interaction.followup.send("❌ Сначала зарегистрируйся: /register", ephemeral=True)
            return

        async with await get_db() as db:
            rows = await db.execute_fetchall("SELECT * FROM goods WHERE id=?", (good_id,))
            if not rows:
                await interaction.followup.send("❌ Товар не найден.", ephemeral=True)
                return
            good = rows[0]

            if good["stock"] < quantity:
                await interaction.followup.send(f"❌ Недостаточно товара. В наличии: {good['stock']}.", ephemeral=True)
                return

            total = good["price_isk"] * quantity
            if balance_data["isk_balance"] < total:
                await interaction.followup.send(
                    f"❌ Недостаточно ISK. Нужно {format_isk(total)}, у тебя {format_isk(balance_data['isk_balance'])}.",
                    ephemeral=True,
                )
                return

            await db.execute("UPDATE goods SET stock = stock - ? WHERE id=?", (quantity, good_id))
            await db.execute(
                "INSERT INTO purchases (discord_id, good_id, quantity, total_isk) VALUES (?,?,?,?)",
                (interaction.user.id, good_id, quantity, total),
            )
            await db.commit()

        new_balance = await update_isk(
            interaction.user.id, -total, note=f"Purchase: {good['name']} x{quantity}"
        )

        embed = discord.Embed(title="✅ Покупка совершена", color=discord.Color.green())
        embed.add_field(name="Товар", value=good["name"], inline=True)
        embed.add_field(name="Количество", value=str(quantity), inline=True)
        embed.add_field(name="Стоимость", value=format_isk(total), inline=True)
        embed.add_field(name="Остаток баланса", value=format_isk(new_balance), inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

        guild = interaction.guild
        if LOG_CHANNEL_ID and (log_ch := guild.get_channel(LOG_CHANNEL_ID)):
            await log_ch.send(
                f"🛒 {interaction.user.mention} купил **{good['name']} x{quantity}** за {format_isk(total)}"
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Goods(bot))
