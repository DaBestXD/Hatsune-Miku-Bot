import sys
from botconfig.bot import botsetup
from botconfig.loggerConfig import logger_config
from botextras.loadenv_values import load_env_vals



def main(args: list[str]) -> None:
    if len(args) <=1:
        load_env_vals()
    elif args[1] == "-d" or args[1] == "-docker":
        print("Docker usage.")
    else:
        print("Usage is -d or -docker.")
        return None
    logger_config()
    bot, token = botsetup()
    bot.run(token=token, log_handler=None)

if __name__ == "__main__":
    main(sys.argv)
