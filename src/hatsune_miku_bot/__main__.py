import argparse
import asyncio
import contextlib

from bot_status.db_stuff.db_logic import db_init, snapshot_loop
from hatsune_miku_bot.bot_config.client import botsetup
from hatsune_miku_bot.bot_config.logging_config import logger_config


class CmdArgs(argparse.Namespace):
    debugger_enabled: bool
    docker_enabled: bool


def args() -> CmdArgs:
    parser = argparse.ArgumentParser(color=True)
    parser.add_argument(
        "--debugger_enabled",
        help="Launch bot with debug commands",
        action="store_true",
    )
    return parser.parse_args(namespace=CmdArgs())


async def main() -> None:
    await db_init()
    cmd_args = args()
    logger_config()
    bot, token = botsetup(cmd_args.debugger_enabled)
    snapshot_task = asyncio.create_task(snapshot_loop(bot))
    try:
        await bot.start(token=token)
    finally:
        snapshot_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await snapshot_task
        await bot.close()


def run() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    run()
