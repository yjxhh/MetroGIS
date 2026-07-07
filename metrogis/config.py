from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CACHE_DIR = ROOT / "cache"

LOG_DIR = ROOT / "logs"

CACHE_DIR.mkdir(exist_ok=True)

LOG_DIR.mkdir(exist_ok=True)