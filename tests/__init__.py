import os

# Keep test module imports deterministic. python-dotenv does not overwrite
# environment variables that are already set, so local .env credentials cannot
# change test behavior.
os.environ.update(
    {
        "DISCORD_TOKEN": "test-token",
        "GUILD_ID": "1",
        "USER_ID": "1",
        "SPOTIFY_CLIENT_ID": "",
        "SPOTIFY_CLIENT_SECRET": "",
    }
)
