from botconfig.bot import botsetup
from botconfig.loggerConfig import logger_config
from botextras.loadenv_values import load_env_vals



def main() -> None:
    load_env_vals()
    logger_config()
    bot, token = botsetup()
    bot.run(token=token, log_handler=None)

if __name__ == "__main__":
    main()
