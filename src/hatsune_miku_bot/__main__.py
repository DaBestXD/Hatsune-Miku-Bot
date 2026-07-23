import argparse
import asyncio
import contextlib
import os

from hatsune_miku_bot.bot_config.client import botsetup
from hatsune_miku_bot.db_logging.db_main import DBLogic
from hatsune_miku_bot.logging import setup_logging


class CmdArgs(argparse.Namespace):
    debugger_enabled: bool
    json_logging: bool
    prod_enabled: bool


def args() -> CmdArgs:
    parser = argparse.ArgumentParser(color=True)
    parser.add_argument(
        "--debugger_enabled",
        help="Launch bot with debug commands",
        action="store_true",
    )
    parser.add_argument(
        "--json_logging",
        help="Launch the bot with json logging",
        action="store_true",
    )
    parser.add_argument(
        "--prod_enabled",
        help="Launch bot with prod as environment",
        action="store_true",
    )
    return parser.parse_args(namespace=CmdArgs())


async def main(debugger_enabled: bool) -> None:
    db = await DBLogic.async_init()
    try:
        bot, token = botsetup(db, debugger_enabled)
        async with bot:
            await bot.start(token)
    finally:
        await db.close()


def run() -> None:
    cmd_args = args()
    os.environ["APP_ENVIRONMENT"] = "PROD" if cmd_args.prod_enabled else "DEV"
    os.environ["LOG_FORMAT"] = "json" if cmd_args.json_logging else "color"
    listner = setup_logging()
    with contextlib.suppress(KeyboardInterrupt), listner:
        asyncio.run(main(cmd_args.debugger_enabled))


if __name__ == "__main__":
    raise SystemExit(run())
