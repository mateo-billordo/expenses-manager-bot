"""Bot configuration loaded from environment variables and messages.json."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "expenses.db"
RECEIPTS_DIR = DATA_DIR / "receipts"
MESSAGES_PATH = BASE_DIR / "messages.json"

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
_allowed_env: list[int] = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USERS", "").split(",")
    if uid.strip()
]
ALLOWED_USERS: list[int] = list(set(_allowed_env + [ADMIN_ID])) if ADMIN_ID else _allowed_env
GROUP_CHAT_ID: int = int(os.getenv("GROUP_CHAT_ID", "0"))
PENDING_TIMEOUT: int = int(os.getenv("PENDING_TIMEOUT", "600"))


def _load_messages() -> dict[str, str]:
    """Load UI strings from messages.json."""
    if MESSAGES_PATH.exists():
        with open(MESSAGES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


MESSAGES: dict[str, str] = _load_messages()


def msg(key: str, **kwargs: object) -> str:
    """Get a message string with optional formatting."""
    template = MESSAGES.get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template


def ensure_directories() -> None:
    """Create required data directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
