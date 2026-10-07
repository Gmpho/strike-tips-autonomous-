"""One-off re-embed migration for embedding-space changes (Oct-2026:
embeddinggemma:300m -> embeddinggemma-2:270m).

Copies every document from the legacy collections into the versioned ones;
Chroma re-embeds on add with the active function. Idempotent (upserts by id)
and dry-run by default.

Usage:
  python -m core_agent.db.reembed                  # dry run (counts only)
  python -m core_agent.db.reembed --live           # migrate
  python -m core_agent.db.reembed --live --data-dir /app/data
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

logger = logging.getLogger("reembed")
BATCH = 100


def migrate(data_dir: str, live: bool, cloud: bool = False) -> int:
    import chromadb
    from core_agent.skills.memory.chroma_memory import (
        _make_embedding_fn,
        collection_names,
    )

    new_cols = collection_names()
    if new_cols["form"] == "form_insights":
        print("Active embedder is still v1 — nothing to migrate. "
              "Pull embeddinggemma-2:270m or set MODEL_EMBEDDER first.")
        return 0

    chroma_api_key = os.getenv("CHROMA_API_KEY", "")
    chroma_host = os.getenv("CHROMA_HOST", "")
    if cloud or (chroma_api_key and chroma_host):
        from chromadb import DEFAULT_TENANT
        client = chromadb.HttpClient(
            host=chroma_host, ssl=True,
            headers={"x-chroma-token": chroma_api_key},
            tenant=os.getenv("CHROMA_TENANT", "") or DEFAULT_TENANT,
            database=os.getenv("CHROMA_DATABASE", "default_database"),
        )
    else:
        client = chromadb.PersistentClient(path=data_dir)

    try:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        old_form = client.get_collection(
            "form_insights", embedding_function=DefaultEmbeddingFunction())
        old_chat = client.get_collection(
            "chat_history", embedding_function=DefaultEmbeddingFunction())
    except Exception as e:
        print(f"No legacy collections found ({e}) — nothing to migrate.")
        return 0

    total = 0
    for old_name, new_name in (("form_insights", new_cols["form"]),
                               ("chat_history", new_cols["chat"])):
        old = old_form if old_name == "form_insights" else old_chat
        n = old.count()
        print(f"[dry-run={not live}] {old_name}: {n} docs -> {new_name}")
        if not live or n == 0:
            total += n
            continue
        new_col = client.get_or_create_collection(
            name=new_name, metadata={"hnsw:space": "cosine"},
            embedding_function=_make_embedding_fn())
        offset = 0
        moved = 0
        while True:
            got = old.get(limit=BATCH, offset=offset,
                          include=["documents", "metadatas"])
            ids = got.get("ids", [])
            if not ids:
                break
            new_col.upsert(ids=ids, documents=got.get("documents"),
                           metadatas=got.get("metadatas"))
            moved += len(ids)
            offset += len(ids)
        print(f"  migrated {moved} docs")
        total += moved
    if live:
        print(f"Done. Legacy collections left intact (delete manually after verifying).")
    else:
        print("Dry run complete — nothing written. Re-run with --live.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--data-dir", default=os.getenv("CHROMA_DIR", "data/chroma"))
    ap.add_argument("--cloud", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return migrate(args.data_dir, args.live, args.cloud)


if __name__ == "__main__":
    sys.exit(main())
