"""Database layer: connection, schema creation, and helpers."""

from __future__ import annotations

import os
import aiosqlite

from config import DB_PATH

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _create_schema(_db)
    return _db


async def _create_schema(db: aiosqlite.Connection) -> None:
    await db.executescript("""
    PRAGMA journal_mode=WAL;
    PRAGMA foreign_keys=ON;

    -- Users registered in the corporation ─────────────────────────────────────
    CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY,   -- Telegram user_id
        username        TEXT,
        ingame_name     TEXT NOT NULL,
        corp_role       TEXT NOT NULL DEFAULT 'pilot',
        balance         REAL NOT NULL DEFAULT 0.0,
        pvp_score       INTEGER NOT NULL DEFAULT 0,
        pve_score       INTEGER NOT NULL DEFAULT 0,
        industry_score  INTEGER NOT NULL DEFAULT 0,
        registered_at   TEXT NOT NULL DEFAULT (datetime('now')),
        approved        INTEGER NOT NULL DEFAULT 0  -- 0=pending, 1=approved, 2=rejected
    );

    -- Activity reports parsed from screenshots ────────────────────────────────
    CREATE TABLE IF NOT EXISTS activity_reports (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        category    TEXT NOT NULL,   -- 'pvp' | 'pve' | 'loot'
        amount      REAL NOT NULL DEFAULT 0.0,
        description TEXT,
        screenshot  TEXT,            -- file_id stored by Telegram
        approved    INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Balance transactions ────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS transactions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        delta       REAL NOT NULL,
        reason      TEXT,
        admin_id    INTEGER,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Corp orders ─────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS orders (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        description TEXT,
        reward      REAL NOT NULL DEFAULT 0.0,
        status      TEXT NOT NULL DEFAULT 'open',  -- open | in_progress | done | cancelled
        created_by  INTEGER NOT NULL,
        assigned_to INTEGER,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- News broadcasts ─────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS news (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        body        TEXT NOT NULL,
        author_id   INTEGER NOT NULL,
        sent        INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Guides ──────────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS guides (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        content     TEXT NOT NULL,
        category    TEXT NOT NULL DEFAULT 'general',
        author_id   INTEGER NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """)
    await db.commit()
