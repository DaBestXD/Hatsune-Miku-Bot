from pathlib import Path


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src").is_dir():
            return parent
    return Path.cwd()


PROJECT_ROOT = _project_root()
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = PACKAGE_ROOT / "assets"
ENV_PATH = PROJECT_ROOT / ".env"
OPTIONAL_VALUES = {"SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "USER_ID", "GUILD_ID"}
