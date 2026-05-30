import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from core_agent.config.paths import DATA_DIR

logger = logging.getLogger("dream-memory")

MEMORY_DIR = DATA_DIR / "memory"
os.makedirs(MEMORY_DIR, exist_ok=True)


def write_memory(
    category: str,
    title: str,
    body: str,
    tags: Optional[list] = None,
):
    """Append a structured memory entry to a MEMORY.md file.
    Each file is a flat markdown file with ##-separated entries.
    Used by DreamEngine for two-phase memory persistence."""

    path = MEMORY_DIR / f"{category}.md"
    tags_line = ", ".join(tags) if tags else ""
    entry_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"## {title}\n"
        f"- **Date**: {entry_ts}\n"
        f"- **Tags**: {tags_line}\n"
        f"- **Body**: {body}\n\n"
    )
    with open(path, "a") as f:
        f.write(entry)
    logger.info("Wrote memory [%s] %s", category, title)


def read_memories(category: str, limit: int = 5) -> list[dict]:
    """Read the most recent N entries from a MEMORY.md file."""

    path = MEMORY_DIR / f"{category}.md"
    if not path.exists():
        return []

    with open(path) as f:
        content = f.read()

    entries = []
    for block in content.split("## "):
        if not block.strip():
            continue
        lines = block.strip().splitlines()
        entry = {"title": lines[0].strip() if lines else ""}
        for line in lines[1:]:
            if line.startswith("- **Date**:"):
                entry["date"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **Tags**:"):
                entry["tags"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **Body**:"):
                entry["body"] = line.split(":", 1)[1].strip()
        entries.append(entry)

    return entries[-limit:]


def trim_memories(category: str, max_entries: int = 100):
    """Keep only the most recent max_entries in a MEMORY.md file."""

    path = MEMORY_DIR / f"{category}.md"
    if not path.exists():
        return

    with open(path) as f:
        content = f.read()

    blocks = content.split("## ")
    header = blocks[0]  # anything before first ##
    entries = blocks[1:]

    if len(entries) <= max_entries:
        return

    with open(path, "w") as f:
        f.write(header)
        for block in entries[-max_entries:]:
            f.write("## " + block)

    logger.info("Trimmed %s to %d entries", category, max_entries)
