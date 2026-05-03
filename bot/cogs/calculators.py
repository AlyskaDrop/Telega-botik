"""
Cog: Calculators
All Eve Echoes in-game calculators:
  /calc_profit     – profit from selling mined/looted items
  /calc_implant    – optimal implant set for a given skill level
  /calc_mining     – estimated mining yield per hour
  /calc_production – materials needed to produce a ship / module
"""

from __future__ import annotations

import math
import discord
from discord import app_commands
from discord.ext import commands

from bot.config import GUILD_ID
from bot.utils.helpers import format_isk


# ── Static data (representative Eve Echoes values) ────────────────────────────

# Mining yield table: {ship_name: base_m3_per_cycle, cycle_sec}
MINING_SHIPS: dict[str, tuple[float, int]] = {
    "Venture":          (60.0,  60),
    "Procurer":         (120.0, 60),
    "Retriever":        (140.0, 60),
    "Mackinaw":         (170.0, 60),
    "Covetor":          (200.0, 60),
    "Hulk":             (240.0, 60),
    "Orca":             (80.0,  60),
}

# Production: {item_name: {material: qty, ...}}
PRODUCTION_RECIPES: dict[str, dict[str, int]] = {
    "Frigate T1":      {"Tritanium": 20_000,  "Pyerite": 5_000},
    "Destroyer T1":    {"Tritanium": 50_000,  "Pyerite": 10_000, "Mexallon": 3_000},
    "Cruiser T1":      {"Tritanium": 120_000, "Pyerite": 30_000, "Mexallon": 10_000, "Isogen": 2_000},
    "Battlecruiser T1":{"Tritanium": 300_000, "Pyerite": 80_000, "Mexallon": 25_000, "Isogen": 6_000, "Nocxium": 1_000},
    "Battleship T1":   {"Tritanium": 800_000, "Pyerite": 200_000,"Mexallon": 60_000, "Isogen": 15_000,"Nocxium": 3_000,"Zydrine": 500},
}

# Implant bonus table: {level: bonus_percent}
IMPLANT_BONUSES = {
    1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0,
    6: 6.0, 7: 7.0, 8: 8.0, 9: 9.0, 10: 10.0,
}


class Calculators(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /calc_profit ───────────────────────────────────────────────────────────
    @app_commands.command(name="calc_profit", description="Калькулятор прибыли от продажи товаров")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def calc_profit(
        self,
        interaction: discord.Interaction,
        buy_price: int,
        sell_price: int,
        quantity: int = 1,
        broker_fee_pct: float = 3.0,
        tax_pct: float = 1.5,
    ) -> None:
        gross = (sell_price - buy_price) * quantity
        broker_fee = sell_price * quantity * broker_fee_pct / 100
        tax = sell_price * quantity * tax_pct / 100
        net = gross - broker_fee - tax
        margin_pct = net / (buy_price * quantity) * 100 if buy_price else 0

        embed = discord.Embed(title="💹 Калькулятор прибыли", color=discord.Color.green() if net > 0 else discord.Color.red())
        embed.add_field(name="Куплено", value=f"{format_isk(buy_price)} × {quantity}", inline=True)
        embed.add_field(name="Продано", value=f"{format_isk(sell_price)} × {quantity}", inline=True)
        embed.add_field(name="Валовая прибыль", value=format_isk(gross), inline=True)
        embed.add_field(name="Брокерский сбор", value=format_isk(int(broker_fee)), inline=True)
        embed.add_field(name="Налог", value=format_isk(int(tax)), inline=True)
        embed.add_field(name="Чистая прибыль", value=f"**{format_isk(int(net))}** ({margin_pct:.1f}%)", inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /calc_implant ──────────────────────────────────────────────────────────
    @app_commands.command(name="calc_implant", description="Расчёт бонуса импланта по уровню скилла")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def calc_implant(
        self,
        interaction: discord.Interaction,
        implant_slot: int,
        skill_level: int,
        base_attribute: float,
    ) -> None:
        if not (1 <= implant_slot <= 10):
            await interaction.response.send_message("❌ Слот импланта должен быть от 1 до 10.", ephemeral=True)
            return
        if not (1 <= skill_level <= 5):
            await interaction.response.send_message("❌ Уровень скилла должен быть от 1 до 5.", ephemeral=True)
            return

        # Each implant slot gives slot% bonus; skill level multiplies effectiveness
        base_bonus_pct = IMPLANT_BONUSES.get(implant_slot, implant_slot * 1.0)
        effective_bonus_pct = base_bonus_pct * skill_level / 5 * 1.5  # simplified model
        boosted = base_attribute * (1 + effective_bonus_pct / 100)

        embed = discord.Embed(title="🔬 Калькулятор имплантов", color=discord.Color.blurple())
        embed.add_field(name="Слот импланта", value=str(implant_slot), inline=True)
        embed.add_field(name="Уровень скилла", value=str(skill_level), inline=True)
        embed.add_field(name="Базовый бонус слота", value=f"{base_bonus_pct:.1f}%", inline=True)
        embed.add_field(name="Эффективный бонус", value=f"{effective_bonus_pct:.2f}%", inline=True)
        embed.add_field(name="Базовый атрибут", value=f"{base_attribute:.2f}", inline=True)
        embed.add_field(name="Улучшенный атрибут", value=f"**{boosted:.2f}**", inline=True)
        embed.set_footer(text="Расчёт приблизительный; зависит от конкретного типа импланта.")
        await interaction.response.send_message(embed=embed)

    # ── /calc_mining ───────────────────────────────────────────────────────────
    @app_commands.command(name="calc_mining", description="Калькулятор добычи руды в час")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def calc_mining(
        self,
        interaction: discord.Interaction,
        ship: str,
        mining_skill_level: int = 5,
        drone_bonus_pct: float = 0.0,
        ore_isk_per_m3: float = 500.0,
        hours: float = 1.0,
    ) -> None:
        ship_key = ship.strip().title()
        if ship_key not in MINING_SHIPS:
            ships_list = ", ".join(MINING_SHIPS.keys())
            await interaction.response.send_message(
                f"❌ Неизвестный корабль. Доступные: {ships_list}", ephemeral=True
            )
            return

        base_m3, cycle_sec = MINING_SHIPS[ship_key]
        skill_mult = 1 + mining_skill_level * 0.05   # +5% per level
        drone_mult = 1 + drone_bonus_pct / 100
        m3_per_cycle = base_m3 * skill_mult * drone_mult
        cycles_per_hour = 3600 / cycle_sec
        m3_per_hour = m3_per_cycle * cycles_per_hour
        total_m3 = m3_per_hour * hours
        total_isk = total_m3 * ore_isk_per_m3

        embed = discord.Embed(title="⛏️ Калькулятор добычи", color=discord.Color.from_str("#8B4513"))
        embed.add_field(name="Корабль", value=ship_key, inline=True)
        embed.add_field(name="Уровень скилла", value=str(mining_skill_level), inline=True)
        embed.add_field(name="Бонус дронов", value=f"{drone_bonus_pct:.1f}%", inline=True)
        embed.add_field(name="M³ за цикл", value=f"{m3_per_cycle:.1f}", inline=True)
        embed.add_field(name="M³ в час", value=f"{m3_per_hour:,.0f}", inline=True)
        embed.add_field(name=f"M³ за {hours:.1f}ч", value=f"{total_m3:,.0f}", inline=True)
        embed.add_field(name="ISK/m³", value=f"{ore_isk_per_m3:,.0f}", inline=True)
        embed.add_field(name=f"Прибыль за {hours:.1f}ч", value=f"**{format_isk(int(total_isk))}**", inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /calc_production ───────────────────────────────────────────────────────
    @app_commands.command(name="calc_production", description="Материалы для производства корабля/модуля")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def calc_production(
        self,
        interaction: discord.Interaction,
        item: str,
        quantity: int = 1,
        material_efficiency_pct: float = 0.0,
    ) -> None:
        item_key = item.strip().title()
        # fuzzy match
        matched = next((k for k in PRODUCTION_RECIPES if k.lower() == item_key.lower()), None)
        if not matched:
            items_list = ", ".join(PRODUCTION_RECIPES.keys())
            await interaction.response.send_message(
                f"❌ Неизвестный предмет. Доступные: {items_list}", ephemeral=True
            )
            return

        recipe = PRODUCTION_RECIPES[matched]
        me_mult = 1 - material_efficiency_pct / 100

        embed = discord.Embed(
            title=f"🏭 Производство: {matched} × {quantity}",
            color=discord.Color.blurple(),
        )
        for mat, base_qty in recipe.items():
            needed = math.ceil(base_qty * quantity * me_mult)
            embed.add_field(name=mat, value=f"{needed:,}", inline=True)

        if material_efficiency_pct:
            embed.set_footer(text=f"ME {material_efficiency_pct:.1f}% применён")
        await interaction.response.send_message(embed=embed)

    # ── /calc_help ─────────────────────────────────────────────────────────────
    @app_commands.command(name="calc_help", description="Справка по калькуляторам")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def calc_help(self, interaction: discord.Interaction) -> None:
        text = (
            "**💹 /calc_profit** `buy_price sell_price [quantity] [broker_fee_pct] [tax_pct]`\n"
            "> Чистая прибыль после сборов и налогов.\n\n"
            "**🔬 /calc_implant** `implant_slot skill_level base_attribute`\n"
            "> Бонус атрибута от импланта с учётом уровня скилла.\n\n"
            "**⛏️ /calc_mining** `ship [mining_skill_level] [drone_bonus_pct] [ore_isk_per_m3] [hours]`\n"
            f"> Корабли: {', '.join(MINING_SHIPS.keys())}\n\n"
            "**🏭 /calc_production** `item [quantity] [material_efficiency_pct]`\n"
            f"> Предметы: {', '.join(PRODUCTION_RECIPES.keys())}"
        )
        embed = discord.Embed(title="🧮 Калькуляторы Eve Echoes", description=text, color=discord.Color.teal())
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Calculators(bot))
