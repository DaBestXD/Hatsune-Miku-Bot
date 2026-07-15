import logging
import sys
from hatsune_miku_bot.botextras.config import PROJECT_ROOT


class ColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    COLORS = {
        "INFO": "\033[36m",  # cyan
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[35m",  # magenta
        "DEBUG": "\033[37m",  # gray
    }

    def format(self, record):
        original = record.levelname
        color = self.COLORS.get(original, "")
        record.levelname = f"{color}{original}{self.RESET}"
        out = super().format(record)
        record.levelname = original
        return out


def logger_config() -> None:
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "bot.log"

    file_fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    console_fmt = ColorFormatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    file_h = logging.FileHandler(log_path, encoding="utf-8")
    file_h.setFormatter(file_fmt)

    stream_h = logging.StreamHandler(sys.stdout)
    stream_h.setFormatter(console_fmt)

    logging.basicConfig(level=logging.DEBUG, handlers=[file_h, stream_h])
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
