from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = PROJECT_ROOT / "assets"
ENV_PATH = PROJECT_ROOT / ".env"
OPTIONAL_VALUES = {"SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "USER_ID", "GUILD_ID"}
