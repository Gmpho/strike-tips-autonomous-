import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("access-control")


def _whitelist_path() -> Path:
    data_dir = os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent.parent / "data"))
    return Path(data_dir) / "whitelist.json"


def _load_whitelist() -> set:
    path = _whitelist_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return set(data.get("authorized_ids", []))
        except Exception as e:
            logger.warning("Failed to load whitelist: %s", e)
    return set()


def _save_whitelist(ids: set):
    path = _whitelist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"authorized_ids": list(ids)}, indent=2))


def is_authorized(chat_id: int, owner_chat_id: str = "") -> bool:
    whitelist = _load_whitelist()
    if owner_chat_id and str(chat_id) == str(owner_chat_id):
        return True
    return chat_id in whitelist


def authorize(chat_id: int):
    whitelist = _load_whitelist()
    whitelist.add(chat_id)
    _save_whitelist(whitelist)
    logger.info("Authorized chat_id: %s", chat_id)
