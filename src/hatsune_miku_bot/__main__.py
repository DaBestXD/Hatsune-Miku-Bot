import argparse
import asyncio
import contextlib

from hatsune_miku_bot.bot_config.client import botsetup
from hatsune_miku_bot.bot_config.logging_config import logger_config
from hatsune_miku_bot.db_logging.db_main import DBLogic


class CmdArgs(argparse.Namespace):
    debugger_enabled: bool


def args() -> CmdArgs:
    parser = argparse.ArgumentParser(color=True)
    parser.add_argument(
        "--debugger_enabled",
        help="Launch bot with debug commands",
        action="store_true",
    )
    return parser.parse_args(namespace=CmdArgs())


async def main() -> None:
    cmd_args = args()
    logger_config()
    db = await DBLogic.async_init()
    try:
        bot, token = botsetup(db, cmd_args.debugger_enabled)
        async with bot:
            await bot.start(token)
    finally:
        await db.close()


def run() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    run()
