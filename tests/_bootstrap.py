import os
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "hatsune_miku_bot"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("GUILD_ID", "1")
