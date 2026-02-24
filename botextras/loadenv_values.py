from botextras.config import ENV_PATH, OPTIONAL_VALUES
from dotenv import load_dotenv


def env_vals_input(value: str) -> str | None:
    optional = "(Optional value hit enter for none value)" if value in OPTIONAL_VALUES else ""
    while True:
        env_val = input(f"Enter {value}{optional}: ").strip()
        response = input(f"{value}: {env_val} \nCorrect value? (y/n): ")
        if response == "y":
            return env_val


def write_to_env() -> None:
    with ENV_PATH.open("w", encoding="utf-8") as f:
        f.write(f"DISCORD_TOKEN='{env_vals_input('DISCORD_TOKEN')}'\n")
        f.write(f"GUILD_ID='{env_vals_input('GUILD_ID')}'\n")
        f.write(f"SPOTIFY_CLIENT_ID='{env_vals_input('SPOTIFY_CLIENT_ID')}'\n")
        f.write(f"SPOTIFY_CLIENT_SECRET='{env_vals_input('SPOTIFY_CLIENT_SECRET')}'\n")
        f.write(f"USER_ID='{env_vals_input('USER_ID')}'")
    return None


def load_env_vals() -> None:
    if not load_dotenv(dotenv_path=ENV_PATH):
        write_to_env()
    else:
        print("Env values already inputted")
    return None


if __name__ == "__main__":
    load_env_vals()
