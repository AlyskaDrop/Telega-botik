"""
Weeping Ghosts – Eve Echoes Discord Bot
Main entry point.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands

# Ensure the repo root is on the path when run as `python main.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bot.config import DISCORD_TOKEN, GUILD_ID
from bot.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("weeping_ghosts")


COGS = [
    "bot.cogs.registration",
    "bot.cogs.economy",
    "bot.cogs.points",
    "bot.cogs.orders",
    "bot.cogs.goods",
    "bot.cogs.compensation",
    "bot.cogs.ai_agent",
    "bot.cogs.calculators",
    "bot.cogs.killboard",
    "bot.cogs.admin",
    "bot.cogs.auto_roles",
]


class WeepingGhostsBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        # Initialise database
        await init_db()
        log.info("Database initialised.")

        # Load cogs
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("Loaded cog: %s", cog)
            except Exception as exc:
                log.error("Failed to load cog %s: %s", cog, exc)

        # Sync slash commands to the guild
        guild_obj = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild_obj)
        synced = await self.tree.sync(guild=guild_obj)
        log.info("Synced %d slash commands to guild %d", len(synced), GUILD_ID)

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%d)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="Eve Echoes | /help",
            )
        )

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError
    ) -> None:
        log.error("App command error: %s", error, exc_info=error)
        msg = f"❌ Произошла ошибка: {error}"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


async def main() -> None:
    if not DISCORD_TOKEN:
        log.critical("DISCORD_TOKEN is not set. Check your .env file.")
        sys.exit(1)
    if not GUILD_ID:
        log.critical("GUILD_ID is not set. Check your .env file.")
        sys.exit(1)

    bot = WeepingGhostsBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
