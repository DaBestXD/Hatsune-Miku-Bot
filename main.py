import argparse
from botconfig.bot import botsetup
from botconfig.loggerConfig import logger_config
from botextras.loadenv_values import load_env_vals



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-d","--docker",help="Used for docker run.",action="store_true")
    parser.add_argument("-D","--debugger",help="Launch bot with debug commands",action="store_true")
    args = parser.parse_args()
    if not args.docker:
        load_env_vals()
    debug_mode = True if args.debugger else False
    logger_config()
    bot, token = botsetup(debug_mode)
    bot.run(token=token, log_handler=None)

if __name__ == "__main__":
    main()
