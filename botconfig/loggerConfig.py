import logging
import sys

class ColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    COLORS = {
        "INFO": "\033[36m",      # cyan
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[35m",  # magenta
        "DEBUG": "\033[37m",     # gray
    }

    def format(self, record):
        original = record.levelname
        color = self.COLORS.get(original, "")
        record.levelname = f"{color}{original}{self.RESET}"
        out = super().format(record)
        record.levelname = original
        return out

def logger_config() -> None:
    file_fmt = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S')
    console_fmt = ColorFormatter('[%(asctime)s] [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S')

    file_h = logging.FileHandler("./logs/bot.log")
    file_h.setFormatter(file_fmt)

    stream_h = logging.StreamHandler(sys.stdout)
    stream_h.setFormatter(console_fmt)

    logging.basicConfig(level=logging.INFO, handlers=[file_h, stream_h])
