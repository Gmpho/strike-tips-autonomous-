"""
Curated Memory — Frozen snapshot memory files injected into system prompt.
Two files: agent_notes.md (learned patterns) + user_prefs.md (user preferences).
Inspired by Hermes Agent's MEMORY.md + USER.md pattern.
"""

import json
import logging
import os
import fcntl
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("curated-memory")

MEMORY_DIR = Path("data/memory")
AGENT_NOTES_PATH = MEMORY_DIR / "agent_notes.md"
USER_PREFS_PATH = MEMORY_DIR / "user_prefs.md"

MAX_AGENT_NOTES_CHARS = 2200
MAX_USER_PREFS_CHARS = 1375


class CuratedMemory:
    """Manages frozen snapshot memory files with file locking and atomic writes."""

    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        """Create empty memory files if they don't exist."""
        for path in (AGENT_NOTES_PATH, USER_PREFS_PATH):
            if not path.exists():
                path.write_text("")

    def _read_with_lock(self, path: Path) -> str:
        """Read file with shared lock (non-blocking for readers)."""
        try:
            with open(path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                content = f.read()
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return content
        except Exception:
            return ""

    def _write_with_lock(self, path: Path, content: str) -> bool:
        """Write file atomically with exclusive lock."""
        try:
            temp_path = path.with_suffix(path.suffix + ".tmp")
            with open(temp_path, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            temp_path.replace(path)
            return True
        except Exception as e:
            logger.error(f"CuratedMemory write error: {e}")
            return False

    def _truncate_to_limit(self, content: str, max_chars: int) -> str:
        """Truncate to max chars, preserving full lines."""
        if len(content) <= max_chars:
            return content
        truncated = content[:max_chars]
        last_newline = truncated.rfind("\n")
        if last_newline > max_chars * 0.5:
            return truncated[:last_newline]
        return truncated

    def get_agent_notes(self) -> str:
        """Get frozen snapshot of agent notes."""
        content = self._read_with_lock(AGENT_NOTES_PATH)
        return self._truncate_to_limit(content, MAX_AGENT_NOTES_CHARS)

    def get_user_prefs(self) -> str:
        """Get frozen snapshot of user preferences."""
        content = self._read_with_lock(USER_PREFS_PATH)
        return self._truncate_to_limit(content, MAX_USER_PREFS_CHARS)

    def append_agent_note(self, note: str) -> bool:
        """Append a note to agent_notes.md (agent's learned patterns)."""
        current = self._read_with_lock(AGENT_NOTES_PATH)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_content = f"{current}\n\n## {timestamp}\n{note.strip()}\n".strip() + "\n"
        return self._write_with_lock(AGENT_NOTES_PATH, new_content)

    def append_user_pref(self, pref: str) -> bool:
        """Append a preference to user_prefs.md (user's stated preferences)."""
        current = self._read_with_lock(USER_PREFS_PATH)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_content = f"{current}\n\n## {timestamp}\n{pref.strip()}\n".strip() + "\n"
        return self._write_with_lock(USER_PREFS_PATH, new_content)

    def get_system_prompt_injection(self) -> str:
        """Generate the frozen snapshot injection for system prompt."""
        parts = []
        agent_notes = self.get_agent_notes()
        if agent_notes.strip():
            parts.append(f"=== AGENT MEMORY (frozen snapshot) ===\n{agent_notes}")

        user_prefs = self.get_user_prefs()
        if user_prefs.strip():
            parts.append(f"=== USER PREFERENCES (frozen snapshot) ===\n{user_prefs}")

        if parts:
            return "\n\n" + "\n\n".join(parts)
        return ""


curated_memory = CuratedMemory()