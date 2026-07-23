from __future__ import annotations

import copy
import json
import logging
import os
from datetime import UTC, datetime
from logging.config import dictConfig
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, override

from yt_dlp import YoutubeDL

from hatsune_miku_bot.bot_config.paths import PROJECT_ROOT

if TYPE_CHECKING:
    from logging.config import _DictConfigArgs
else:
    _DictConfigArgs = dict[str, Any]

CONFIG_PATH = Path(__file__).with_name("logging_config.json")

_StrMapping = dict[str, str]


class ColorFormatter(logging.Formatter):
    COLORS: Final[_StrMapping] = {
        "INFO": "\033[36m",  # cyan
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[35m",  # magenta
        "DEBUG": "\033[37m",  # gray
    }
    RESET: Final = "\033[0m"

    @override
    def format(self, record: logging.LogRecord) -> str:
        record = copy.copy(record)
        color = self.COLORS[record.levelname]
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class JsonFormatter(logging.Formatter):
    def __init__(
        self,
        service: str,
        environment: str,
        fmt_keys: _StrMapping,
    ) -> None:
        super().__init__()
        self.service = service
        self.environment = environment
        self.fmt_keys = fmt_keys

    @override
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC)
        field_values: dict[str, object] = {
            "timestamp": timestamp.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "service": self.service,
            "environment": self.environment,
            "message": record.getMessage(),
        }

        if record.exc_info:
            field_values["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            field_values["stack"] = self.formatStack(record.stack_info)

        output: dict[str, object] = {}
        for output_key, record_key in self.fmt_keys.items():
            try:
                value = field_values[record_key]
            except KeyError:
                value = getattr(record, record_key, None)

            if value is not None:
                output[output_key] = value

        return json.dumps(output, ensure_ascii=False, default=str)


class YTDLPLogger:
    _yt_dlp_logger = logging.getLogger("yt_dlp")

    def __init__(self, ydl: YoutubeDL | None = None) -> None: ...

    def debug(self, message: str) -> None: ...
    def info(self, message: str) -> None: ...
    def warning(
        self, message: str, *, once: bool = False, only_once: bool = False
    ) -> None: ...
    def error(self, message: str) -> None: ...

    def stdout(self, message: str) -> None: ...
    def stderr(self, message: str) -> None: ...


class MikuQueueHandler(QueueHandler):
    @override
    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        # spooky copy 🙀
        prepared = copy.copy(record)
        prepared.message = record.getMessage()
        prepared.msg = prepared.message
        prepared.args = None
        return prepared


def _load_logging_config() -> _DictConfigArgs:
    with CONFIG_PATH.open() as config_file:
        return json.load(config_file)


def setup_logging() -> QueueListener:
    app_env = os.environ["APP_ENVIRONMENT"]
    if app_env not in ("PROD", "DEV"):
        raise RuntimeError("Invalid runtime value must be PROD or DEV")
    log_format = os.environ["LOG_FORMAT"]
    if log_format not in ("json", "color"):
        raise RuntimeError("Invalid runtime value must be json or color")
    config = _load_logging_config()
    log_level = logging.DEBUG if app_env == "DEV" else logging.INFO
    config["formatters"]["json"]["environment"] = app_env  # type: ignore
    config["handlers"]["stdout"]["level"] = log_level
    config["handlers"]["stdout"]["formatter"] = log_format
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    config["handlers"]["file"]["filename"] = str(log_dir / "bot.log")
    config["handlers"]["file"]["level"] = log_level
    config["handlers"]["file"]["formatter"] = (
        "json" if log_format == "json" else "file"
    )
    config["handlers"]["mikuqueue"]["handlers"].append("file")
    config["root"]["level"] = log_level
    dictConfig(config)
    queue = logging.getHandlerByName("mikuqueue")
    if not isinstance(queue, QueueHandler):
        raise RuntimeError(f"{MikuQueueHandler.__name__} not configured")
    assert queue.listener, "Queue listener was not configured"
    return queue.listener
