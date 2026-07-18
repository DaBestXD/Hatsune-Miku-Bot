import argparse
import asyncio
import contextlib

from hatsune_miku_bot.bot_config.client import botsetup
from hatsune_miku_bot.bot_config.logging_config import logger_config


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
    bot, token = botsetup(cmd_args.debugger_enabled)
    try:
        await bot.start(token=token)
    finally:
        await bot.close()


def run() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    run()
