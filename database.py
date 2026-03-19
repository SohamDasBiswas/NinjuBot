import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "/app/data/ninjubot.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Currency table
    c.execute("""
        CREATE TABLE IF NOT EXISTS currency (
            key TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 100,
            last_daily REAL DEFAULT 0,
            last_work REAL DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )
    """)

    # XP / Levels table
    c.execute("""
        CREATE TABLE IF NOT EXISTS xp (
            key TEXT PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized")

# ── Currency helpers ──────────────────────────────────────────────────────────

def get_balance(guild_id, user_id):
    key = f"{guild_id}_{user_id}"
    conn = get_conn()
    row = conn.execute("SELECT * FROM currency WHERE key=?", (key,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"key": key, "balance": 100, "last_daily": 0, "last_work": 0, "wins": 0, "losses": 0}

def set_balance(guild_id, user_id, data):
    key = f"{guild_id}_{user_id}"
    conn = get_conn()
    conn.execute("""
        INSERT INTO currency (key, balance, last_daily, last_work, wins, losses)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            balance=excluded.balance,
            last_daily=excluded.last_daily,
            last_work=excluded.last_work,
            wins=excluded.wins,
            losses=excluded.losses
    """, (key, data.get("balance", 100), data.get("last_daily", 0),
          data.get("last_work", 0), data.get("wins", 0), data.get("losses", 0)))
    conn.commit()
    conn.close()

# ── XP helpers ────────────────────────────────────────────────────────────────

def get_xp(guild_id, user_id):
    key = f"{guild_id}_{user_id}"
    conn = get_conn()
    row = conn.execute("SELECT * FROM xp WHERE key=?", (key,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"key": key, "xp": 0, "level": 0}

def set_xp(guild_id, user_id, data):
    key = f"{guild_id}_{user_id}"
    conn = get_conn()
    conn.execute("""
        INSERT INTO xp (key, xp, level) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET xp=excluded.xp, level=excluded.level
    """, (key, data.get("xp", 0), data.get("level", 0)))
    conn.commit()
    conn.close()

def get_top_xp(guild_id, limit=10):
    conn = get_conn()
    rows = conn.execute("""
        SELECT key, xp, level FROM xp
        WHERE key LIKE ?
        ORDER BY xp DESC LIMIT ?
    """, (f"{guild_id}_%", limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_top_currency(guild_id, limit=10):
    conn = get_conn()
    rows = conn.execute("""
        SELECT key, balance FROM currency
        WHERE key LIKE ?
        ORDER BY balance DESC LIMIT ?
    """, (f"{guild_id}_%", limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
