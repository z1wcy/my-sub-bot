import os
import asyncpg
from datetime import datetime, timedelta

DATABASE_URL = os.getenv("DATABASE_URL")

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id BIGINT PRIMARY KEY,
                expires_at TIMESTAMP NOT NULL,
                payment_method TEXT,
                tx_hash TEXT UNIQUE
            )
        """)


async def save_subscription(user_id: int, days: int, method: str, tx_hash: str = None):
    expires = datetime.now() + timedelta(days=days)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO subscriptions (user_id, expires_at, payment_method, tx_hash)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
            SET expires_at = EXCLUDED.expires_at,
                payment_method = EXCLUDED.payment_method,
                tx_hash = EXCLUDED.tx_hash
            """,
            user_id, expires, method, tx_hash
        )


async def get_subscription(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT expires_at FROM subscriptions WHERE user_id = $1",
            user_id
        )
        if row and row["expires_at"]:
            return row["expires_at"].isoformat()
        return None


async def get_expired_users():
    """Возвращает список user_id, у которых подписка закончилась."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id FROM subscriptions WHERE expires_at < $1",
            datetime.now()
        )
        return [row["user_id"] for row in rows]


async def get_expiring_soon(days: int = 3):
    """Возвращает user_id, у которых подписка закончится через N дней."""
    pool = await get_pool()
    now = datetime.now()
    soon = now + timedelta(days=days)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id FROM subscriptions
            WHERE expires_at > $1 AND expires_at < $2
            """,
            now, soon
        )
        return [row["user_id"] for row in rows]


async def delete_subscription(user_id: int):
    """Удаляет запись о подписке (после кика из канала)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM subscriptions WHERE user_id = $1",
            user_id
        )


async def get_stats():
    """Статистика: всего активных, всего записей."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        active = await conn.fetchval(
            "SELECT COUNT(*) FROM subscriptions WHERE expires_at > $1",
            datetime.now()
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM subscriptions")
        return {"active": active, "total": total}