import aiosqlite
from datetime import datetime, timedelta

DB_PATH = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                expires_at TEXT NOT NULL,
                payment_method TEXT,
                tx_hash TEXT UNIQUE
            )
        """)
        await db.commit()

async def save_subscription(user_id: int, days: int, method: str, tx_hash: str = None):
    expires = (datetime.now() + timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO subscriptions (user_id, expires_at, payment_method, tx_hash) VALUES (?, ?, ?, ?)",
            (user_id, expires, method, tx_hash)
        )
        await db.commit()

async def get_subscription(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT expires_at FROM subscriptions WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None