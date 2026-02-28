from botconfig.bot import botsetup 
from botconfig.loggerConfig import logger_config



def main() -> None:
    logger_config()
    bot, token = botsetup()
    bot.run(token=token, log_handler=None)

if __name__ == "__main__":
    main()
