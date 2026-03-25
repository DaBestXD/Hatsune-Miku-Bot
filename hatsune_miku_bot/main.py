import argparse
import asyncio
import contextlib
from botconfig.bot import botsetup
from botconfig.loggerConfig import logger_config
from botextras.loadenv_values import load_env_vals
from db_stuff.db_logic import db_init, snapshot_loop


async def main() -> None:
    await db_init()
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--docker", help="Used for docker run.", action="store_true")
    parser.add_argument("-D", "--debugger", help="Launch bot with debug commands", action="store_true")
    args = parser.parse_args()
    if not args.docker:
        load_env_vals()
    debug_mode = True if args.debugger else False
    logger_config()
    bot, token = botsetup(debug_mode)
    snapshot_task = asyncio.create_task(snapshot_loop(bot))
    try:
        await bot.start(token=token)
    finally:
        snapshot_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await snapshot_task
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
