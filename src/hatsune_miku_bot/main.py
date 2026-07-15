import argparse
import asyncio
import contextlib

from hatsune_miku_bot.bot_config.client import botsetup
from hatsune_miku_bot.bot_config.env_loader import load_env_vals
from hatsune_miku_bot.bot_config.logging_config import logger_config
from hatsune_miku_bot.db_stuff.db_logic import db_init, snapshot_loop


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d", "--docker", help="Used for docker run.", action="store_true"
    )
    parser.add_argument(
        "-D",
        "--debugger",
        help="Launch bot with debug commands",
        action="store_true",
    )
    return parser.parse_args()


async def main() -> None:
    await db_init()
    cmd_args = args()
    if not cmd_args.docker:
        load_env_vals()
    debug_mode = True if cmd_args.debugger else False
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


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
