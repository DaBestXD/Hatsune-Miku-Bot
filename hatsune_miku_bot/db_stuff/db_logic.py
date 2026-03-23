import aiosqlite
import asyncio
from botextras.constants import DB_PATH
from typing import TYPE_CHECKING, Literal
from db_stuff.db_schema import CREATE_EVENTS, CREATE_SNAPSHOTS
from datetime import datetime, timezone
if TYPE_CHECKING:
    from botconfig.bot import Bot
async def db_init():
    async with aiosqlite.connect(DB_PATH) as con:
        await con.execute(CREATE_EVENTS)
        await con.execute(CREATE_SNAPSHOTS)
        await con.commit()

async def insert_event(event_type: str, event_time: str, details: str|None = None) -> None:
    async with aiosqlite.connect(DB_PATH) as con:
        query = """
            INSERT INTO events(event_type, event_time, details)
            VALUES(:event_type, :event_time, :details)
        """
        args = {
            "event_type" : event_type,
            "event_time" : event_time,
            "details" : details
        }
        await con.execute(query, args)
        await con.commit()

async def insert_snapshot(snapshot_time: str, status:
                          Literal["online","degraded","down"],discord_connection: Literal[0,1],
                          latency_ms: float|None, uptime_seconds: int) -> None:
    async with aiosqlite.connect(DB_PATH) as con:
        query = """
            INSERT INTO snapshots(snapshot_time, status, discord_connection, latency_ms, uptime_seconds)
            VALUES(:snapshot_time, :status, :discord_connection, :latency_ms, :uptime_seconds)
        """
        args = {
            "snapshot_time" : snapshot_time,
            "status" : status,
            "discord_connection" : discord_connection,
            "latency_ms" : latency_ms,
            "uptime_seconds" : uptime_seconds
        }
        await con.execute(query, args)
        await con.commit()


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)

def get_bot_status(bot: Bot) -> Literal["online", "degraded", "down"]:
    if not bot.is_ready():
        return "down"
    if bot.latency * 1000 >= 1000:
        return "degraded"
    return "online"

async def snapshot_loop(bot: Bot):
    while True:
        try:
            latency = round(bot.latency * 1000, 2) if bot.is_ready() else None
            connection = 1 if bot.is_ready() else 0
            cur_uptime = int((utc_now_dt() - bot.process_start).total_seconds())
            await insert_snapshot(
                snapshot_time=utc_now_dt().isoformat(),
                status=get_bot_status(bot),
                discord_connection=connection,
                latency_ms=latency,
                uptime_seconds=cur_uptime
            )
        except Exception as e:
            print(f"Snapshot loop error: {e}")
        await asyncio.sleep(60)
