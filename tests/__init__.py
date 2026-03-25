import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "hatsune_miku_bot"

for path in (REPO_ROOT, PACKAGE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("GUILD_ID", "1")
