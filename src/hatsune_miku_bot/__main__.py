from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os

from hatsune_miku_bot.bot_config.client import botsetup
from hatsune_miku_bot.db_logging.db_main import DBLogic
from hatsune_miku_bot.logging import setup_logging
from hatsune_miku_bot.monitoring.factory import init_monitor


class CmdArgs(argparse.Namespace):
    debugger_enabled: bool
    json_logging: bool
    prod_enabled: bool
    prometheus_enabled: bool


logger = logging.getLogger(__name__)


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
    parser.add_argument(
        "--prometheus_enabled",
        help="Launch bot with the prometheus metrics enabled",
        action="store_true",
    )
    return parser.parse_args(namespace=CmdArgs())


async def main(debugger_enabled: bool, prometheus_enabled: bool) -> None:
    monitor = init_monitor(enabled=prometheus_enabled)
    monitor.start()
    db = await DBLogic.async_init()
    try:
        bot, token = botsetup(db, debugger_enabled, monitor)
        async with bot:
            await bot.start(token)
    finally:
        await db.close()
        monitor.close()


def run() -> None:
    cmd_args = args()
    os.environ["APP_ENVIRONMENT"] = "PROD" if cmd_args.prod_enabled else "DEV"
    os.environ["LOG_FORMAT"] = "json" if cmd_args.json_logging else "color"
    listner = setup_logging()
    with contextlib.suppress(KeyboardInterrupt), listner:
        asyncio.run(
            main(cmd_args.debugger_enabled, cmd_args.prometheus_enabled)
        )


if __name__ == "__main__":
    raise SystemExit(run())
