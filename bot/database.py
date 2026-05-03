"""
Database layer – thin async wrapper around aiosqlite.
All table definitions live here; call `init_db()` once at startup.
"""

from __future__ import annotations

import aiosqlite
from bot.config import DB_PATH


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    async with await get_db() as db:
        await db.executescript("""
        -- ── Members ───────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS members (
            discord_id   INTEGER PRIMARY KEY,
            pilot_name   TEXT    NOT NULL,
            joined_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            is_verified  INTEGER NOT NULL DEFAULT 0
        );

        -- ── Economy ───────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS balances (
            discord_id   INTEGER PRIMARY KEY REFERENCES members(discord_id),
            isk_balance  INTEGER NOT NULL DEFAULT 0,
            pvp_points   INTEGER NOT NULL DEFAULT 0,
            pve_points   INTEGER NOT NULL DEFAULT 0
        );

        -- ── ISK / Points transactions ─────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS transactions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id   INTEGER NOT NULL REFERENCES members(discord_id),
            type         TEXT    NOT NULL,   -- 'isk_credit','pvp','pve','compensation'
            amount       INTEGER NOT NULL,
            note         TEXT,
            approved_by  INTEGER,            -- admin discord_id or NULL if auto
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- ── Corp orders ───────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT    NOT NULL,
            description  TEXT,
            reward_isk   INTEGER NOT NULL DEFAULT 0,
            status       TEXT    NOT NULL DEFAULT 'open',  -- open/completed/cancelled
            created_by   INTEGER NOT NULL,
            assigned_to  INTEGER,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- ── Corp goods / shop ─────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS goods (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT    NOT NULL,
            description  TEXT,
            price_isk    INTEGER NOT NULL DEFAULT 0,
            stock        INTEGER NOT NULL DEFAULT 0,
            added_by     INTEGER NOT NULL,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- ── Shop purchases ────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS purchases (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id   INTEGER NOT NULL REFERENCES members(discord_id),
            good_id      INTEGER NOT NULL REFERENCES goods(id),
            quantity     INTEGER NOT NULL DEFAULT 1,
            total_isk    INTEGER NOT NULL,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- ── Killboard ─────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS kills (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id   INTEGER NOT NULL REFERENCES members(discord_id),
            pilot_name   TEXT    NOT NULL,
            ship_name    TEXT,
            victim_name  TEXT,
            victim_ship  TEXT,
            system       TEXT,
            isk_value    INTEGER NOT NULL DEFAULT 0,
            kill_type    TEXT    NOT NULL DEFAULT 'pvp',  -- pvp / loss
            screenshot   TEXT,
            verified     INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- ── Compensation claims ───────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS compensations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id   INTEGER NOT NULL REFERENCES members(discord_id),
            ship_name    TEXT,
            isk_value    INTEGER NOT NULL DEFAULT 0,
            payout_isk   INTEGER NOT NULL DEFAULT 0,
            screenshot   TEXT,
            status       TEXT    NOT NULL DEFAULT 'pending',  -- pending/approved/rejected
            reviewed_by  INTEGER,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- ── OCR screenshot log ────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS screenshot_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id   INTEGER,
            purpose      TEXT,
            url          TEXT,
            raw_text     TEXT,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        """)
        await db.commit()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def get_or_create_member(discord_id: int, pilot_name: str) -> None:
    async with await get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO members (discord_id, pilot_name) VALUES (?, ?)",
            (discord_id, pilot_name),
        )
        await db.execute(
            "INSERT OR IGNORE INTO balances (discord_id) VALUES (?)",
            (discord_id,),
        )
        await db.commit()


async def get_balance(discord_id: int) -> dict | None:
    async with await get_db() as db:
        row = await db.execute_fetchall(
            """SELECT m.pilot_name, b.isk_balance, b.pvp_points, b.pve_points
               FROM members m JOIN balances b USING (discord_id)
               WHERE m.discord_id = ?""",
            (discord_id,),
        )
        return dict(row[0]) if row else None


async def update_isk(discord_id: int, amount: int, note: str = "", approved_by: int | None = None) -> int:
    """Add (or subtract) ISK. Returns new balance."""
    async with await get_db() as db:
        await db.execute(
            "UPDATE balances SET isk_balance = isk_balance + ? WHERE discord_id = ?",
            (amount, discord_id),
        )
        await db.execute(
            "INSERT INTO transactions (discord_id, type, amount, note, approved_by) VALUES (?,?,?,?,?)",
            (discord_id, "isk_credit", amount, note, approved_by),
        )
        await db.commit()
        row = await db.execute_fetchall(
            "SELECT isk_balance FROM balances WHERE discord_id = ?", (discord_id,)
        )
        return row[0]["isk_balance"] if row else 0


async def update_points(discord_id: int, pvp: int = 0, pve: int = 0, note: str = "") -> tuple[int, int]:
    """Add PvP / PvE points. Returns (new_pvp, new_pve)."""
    async with await get_db() as db:
        await db.execute(
            "UPDATE balances SET pvp_points = pvp_points + ?, pve_points = pve_points + ? WHERE discord_id = ?",
            (pvp, pve, discord_id),
        )
        if pvp:
            await db.execute(
                "INSERT INTO transactions (discord_id, type, amount, note) VALUES (?,?,?,?)",
                (discord_id, "pvp", pvp, note),
            )
        if pve:
            await db.execute(
                "INSERT INTO transactions (discord_id, type, amount, note) VALUES (?,?,?,?)",
                (discord_id, "pve", pve, note),
            )
        await db.commit()
        row = await db.execute_fetchall(
            "SELECT pvp_points, pve_points FROM balances WHERE discord_id = ?", (discord_id,)
        )
        if row:
            return row[0]["pvp_points"], row[0]["pve_points"]
        return 0, 0
