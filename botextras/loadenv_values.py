from dotenv import load_dotenv


def env_vals_input(value: str) -> str:
    while True:
        env_val = input(f"Enter {value}: ").strip()
        response = input(f"{value}: {env_val} \nCorrect value? (y/n): ")
        if response == "y":
            return env_val


def write_to_env() -> None:
    with open(".env", "w") as f:
        f.write(f"DISCORD_TOKEN='{env_vals_input('DISCORD_TOKEN')}'\n")
        f.write(f"GUILD_ID='{env_vals_input('GUILD_ID')}'\n")
        f.write(f"SPOTIFY_CLIENT_ID='{env_vals_input('SPOTIFY_CLIENT_ID')}'\n")
        f.write(f"SPOTIFY_CLIENT_SECRET='{env_vals_input('SPOTIFY_CLIENT_SECRET')}'")
    return None


def load_env_vals() -> None:
    if not load_dotenv():
        write_to_env()
    else:
        print("Env values already inputted")
    return None


if __name__ == "__main__":
    load_env_vals()
