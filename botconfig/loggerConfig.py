import logging
import sys
from logging import Logger

def logger_config() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler("./logs/bot.log"),
            logging.StreamHandler(sys.stdout)
            ])

