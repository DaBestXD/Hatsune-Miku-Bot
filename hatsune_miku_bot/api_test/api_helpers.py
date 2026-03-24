import aiosqlite
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "status.db"


async def get_status() -> dict[str, str]:
    async with aiosqlite.connect(DB_PATH) as con:
        query = """
            SELECT snapshot_time, status, latency_ms FROM snapshots
            ORDER BY id DESC LIMIT 1
        """
        cols = ["snapshot Time", "status", "latency_ms"]
        cur = await con.execute(query)
        vals = await cur.fetchone()
        if vals:
            return dict(zip(cols, vals))
        return {}


async def uptime_percent_since(hours: int) -> float:
    async with aiosqlite.connect(DB_PATH) as con:
        con.row_factory = aiosqlite.Row
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        query = """
            SELECT discord_connection FROM snapshots
            WHERE snapshot_time >= :cutoff AND uptime_seconds > 0
            ORDER BY id ASC
        """
        cur = await con.execute(query, {"cutoff": cutoff})
        rows = await cur.fetchall()
        if not rows:
            return 0.0
        up_count = sum(row[0] for row in rows)
        return round((up_count / len(list(rows))) * 100, 3)


async def all_uptime_windows() -> dict[str, float]:
    return {
        "hour": await uptime_percent_since(1),
        "day": await uptime_percent_since(24),
        "week": await uptime_percent_since(168),
        "month": await uptime_percent_since(720),
    }


async def last_n_events(n: int) -> dict[str, list[str]]:
    async with aiosqlite.connect(DB_PATH) as con:
        query = """
            SELECT details FROM events LIMIT :n
        """
        args = {"n": n}
        cur = await con.execute(query, args)
        vals = await cur.fetchall()
        if not vals:
            return {f"Last {n} events": []}
        return {f"Last {n} events ": [row[0] for row in vals]}
