import json
import logging
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

from core_agent.config.paths import DATA_DIR

logger = logging.getLogger("jsonl-session")


class JSONLSession:
    """Thread-local append-only JSONL file per user. No embeddings, no vector DB."""

    def __init__(self, user_id: str = "anon_web"):
        self._user_id = user_id
        self._lock = threading.Lock()
        self._session_dir = DATA_DIR / "sessions"
        os.makedirs(self._session_dir, exist_ok=True)
        self._path = self._session_dir / f"{user_id}.jsonl"

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        with self._lock:
            with open(self._path, "a") as f:
                f.write(json.dumps({
                    "role": role,
                    "content": content,
                    "ts": datetime.now().isoformat(),
                    "metadata": metadata or {},
                }) + "\n")

    def get_history(self, limit: int = 20) -> List[Dict]:
        if not self._path.exists():
            return []
        with self._lock:
            with open(self._path) as f:
                lines = f.readlines()
        messages = []
        for line in lines[-limit:]:
            try:
                messages.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
        return messages

    def clear(self) -> None:
        with self._lock:
            if self._path.exists():
                os.remove(self._path)

    def keyword_search(self, query: str, n: int = 5) -> List[Dict]:
        if not self._path.exists():
            return []
        with self._lock:
            with open(self._path) as f:
                lines = f.readlines()
        keywords = query.lower().split()
        results = []
        for line in reversed(lines):
            try:
                msg = json.loads(line.strip())
                content = msg.get("content", "").lower()
                if any(kw in content for kw in keywords):
                    results.append(msg)
                    if len(results) >= n:
                        break
            except json.JSONDecodeError:
                continue
        return results
