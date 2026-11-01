"""
FTS5 Full-Text Search Engine — BM25 ranked + trigram substring matching.
Zero new dependencies (stdlib sqlite3). WAL mode for concurrent reads.
Hybrid search: FTS5 BM25 (0.6) + ChromaDB cosine (0.4).
"""

import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("fts5-search")

FTS5_DB_PATH = os.path.join("data", "search.db")

# Hybrid search weights
HYBRID_KEYWORD_WEIGHT = 0.6
HYBRID_SEMANTIC_WEIGHT = 0.4

_SQL_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS race_data_fts USING fts5(
    content,
    metadata_json,
    source_type UNINDEXED,
    created_at UNINDEXED,
    tokenize='porter unicode61'
)
"""

_SQL_CREATE_TRIGRAM = """
CREATE VIRTUAL TABLE IF NOT EXISTS race_data_trigram USING fts5(
    content,
    metadata_json UNINDEXED,
    source_type UNINDEXED,
    created_at UNINDEXED,
    tokenize='trigram'
)
"""


def _sanitize_fts5_query(raw: str) -> str:
    """Convert user query to safe FTS5 query syntax.

    - Strip special FTS5 operators that could cause syntax errors.
    - Wrap bare words in implicit AND (default FTS5 behavior).
    - Preserve quoted phrases, OR, and NOT.
    """
    if not raw or not raw.strip():
        return ""

    cleaned = raw.strip()

    disallowed = re.findall(r'[+\-*/()]', cleaned)
    for ch in disallowed:
        cleaned = cleaned.replace(ch, " ")

    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


class FTS5Search:
    """Full-text search using SQLite FTS5 with BM25 ranking and trigram fallback."""

    def __init__(self, db_path: str = FTS5_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()

    def _connect(self):
        """Open connection and create tables if needed."""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=OFF")
        self._conn.execute("PRAGMA cache_size=-16384")
        self._conn.execute(_SQL_CREATE_FTS)
        self._conn.execute(_SQL_CREATE_TRIGRAM)
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._connect()
        return self._conn

    # ─── Indexing ───────────────────────────────────────────────────────────

    def index(
        self,
        content: str,
        source_type: str = "form_insight",
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Index a document in both FTS tables. Deduplicates by content hash."""
        if not content or not content.strip():
            return False

        content_stripped = content.strip()[:2000]

        metadata_json = json.dumps(metadata or {}, default=str)

        now = int(time.time())

        try:
            content_hash = hash(content_stripped)
            self.conn.execute(
                "INSERT OR IGNORE INTO race_data_fts(rowid, content, metadata_json, source_type, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (content_hash, content_stripped, metadata_json, source_type, now),
            )
            self.conn.execute(
                "INSERT OR IGNORE INTO race_data_trigram(rowid, content, metadata_json, source_type, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (content_hash, content_stripped, metadata_json, source_type, now),
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"FTS5 index error: {e}")
            return False

    def index_batch(self, documents: List[Dict]) -> int:
        """Index multiple documents. Each dict: {'content': str, 'source_type': str, 'metadata': dict}."""
        count = 0
        for doc in documents:
            if self.index(
                content=doc.get("content", ""),
                source_type=doc.get("source_type", "form_insight"),
                metadata=doc.get("metadata"),
            ):
                count += 1
        return count

    # ─── Search ─────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        n: int = 10,
        source_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """BM25-ranked FTS5 search with trigram fallback for substring matching.

        Args:
            query: Free-text search query.
            n: Max results to return.
            source_type: Optional filter (e.g. 'official_tip', 'dream', 'race_card').

        Returns:
            List of dicts with keys: content, metadata, source_type, score.
        """
        sanitized = _sanitize_fts5_query(query)
        if not sanitized:
            return self._trigram_search(query, n=n, source_type=source_type)

        results = self._bm25_search(sanitized, n=n, source_type=source_type)

        if not results:
            results = self._trigram_search(query, n=n, source_type=source_type)

        return results

    def _bm25_search(
        self,
        query: str,
        n: int = 10,
        source_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """BM25-ranked search via standard FTS5 index."""
        try:
            fts_query = self._build_fts_query(query)
            if not fts_query:
                return []

            sql = (
                "SELECT rowid, content, metadata_json, source_type, bm25(race_data_fts, 0.0, 1.0, 1.0, 1.0) AS score "
                "FROM race_data_fts WHERE race_data_fts MATCH ?"
            )
            params: List[Any] = [fts_query]

            if source_type:
                sql += " AND source_type = ?"
                params.append(source_type)

            sql += " ORDER BY score LIMIT ?"
            params.append(n)

            rows = self.conn.execute(sql, params).fetchall()
            return [
                {
                    "content": row[1],
                    "metadata": json.loads(row[2]) if row[2] else {},
                    "source_type": row[3],
                    "score": round(row[4], 4),
                    "method": "bm25",
                }
                for row in rows
            ]
        except Exception as e:
            logger.debug(f"BM25 search failed (fallback to trigram): {e}")
            return []

    def _trigram_search(
        self,
        query: str,
        n: int = 10,
        source_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Trigram substring search — finds partial/prefix matches."""
        try:
            fts_query = self._build_fts_query(query)
            if not fts_query:
                return []

            sql = (
                "SELECT rowid, content, metadata_json, source_type, rank "
                "FROM race_data_trigram WHERE race_data_trigram MATCH ?"
            )
            params: List[Any] = [fts_query]

            if source_type:
                sql += " AND source_type = ?"
                params.append(source_type)

            sql += " ORDER BY rank LIMIT ?"
            params.append(n)

            rows = self.conn.execute(sql, params).fetchall()
            return [
                {
                    "content": row[1],
                    "metadata": json.loads(row[2]) if row[2] else {},
                    "source_type": row[3],
                    "score": round(float(row[4]), 4),
                    "method": "trigram",
                }
                for row in rows
            ]
        except Exception as e:
            logger.debug(f"Trigram search failed: {e}")
            return []

    @staticmethod
    def _build_fts_query(sanitized: str) -> str:
        """Build an FTS5-safe query from sanitized terms."""
        terms = sanitized.split()
        if not terms:
            return ""

        quoted_phrases = re.findall(r'"([^"]+)"', sanitized)
        for phrase in quoted_phrases:
            sanitized = sanitized.replace(f'"{phrase}"', "")

        keywords = sanitized.split()
        keywords = [k for k in keywords if k.strip()]

        parts = []
        parts.extend(f'"{p}"' for p in quoted_phrases)
        parts.extend(keywords)

        if not parts:
            return ""

        return " AND ".join(parts)

    # ─── Sync from ChromaDB ─────────────────────────────────────────────────

    def sync_from_chroma(self, batch_size: int = 200) -> Dict[str, int]:
        """Re-index all form_insights from ChromaDB into FTS5.

        Tries strike_brain first, then falls back to direct ChromaDB client.

        Returns:
            Dict with total ChromaDB count and newly indexed count.
        """
        collection = None
        try:
            from core_agent.core.strike_brain import brain

            if brain and brain.memory and brain.memory._is_ready:
                collection = brain.memory._form_collection
        except Exception:
            pass

        if collection is None:
            try:
                import chromadb  # noqa: F811
                from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
                chroma_dir = os.getenv("CHROMA_DIR", "data/chroma")
                client = chromadb.PersistentClient(path=chroma_dir)
                collection = client.get_collection(
                    "form_insights", embedding_function=DefaultEmbeddingFunction()
                )
            except Exception as e:
                return {"error": f"ChromaDB not available: {e}"}

        try:
            total = collection.count()
            if total == 0:
                return {"total": 0, "indexed": 0}

            indexed = 0
            offset = 0
            while offset < total:
                batch = collection.get(
                    limit=batch_size,
                    offset=offset,
                    include=["documents", "metadatas"],
                )
                docs = batch.get("documents", [])
                metas = batch.get("metadatas", [])

                for doc, meta in zip(docs, metas):
                    source_type = meta.get("type", "form_insight") if meta else "form_insight"
                    if self.index(content=doc or "", source_type=source_type, metadata=meta):
                        indexed += 1

                offset += batch_size
                logger.info(f"[FTS5] Synced {indexed}/{total}...")

            self.conn.commit()
            return {"total": total, "indexed": indexed}
        except Exception as e:
            logger.error(f"FTS5 sync from ChromaDB failed: {e}")
            return {"error": str(e)}

    # ─── Stats ──────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        try:
            fts_count = self.conn.execute(
                "SELECT COUNT(*) FROM race_data_fts"
            ).fetchone()[0]
            trigram_count = self.conn.execute(
                "SELECT COUNT(*) FROM race_data_trigram"
            ).fetchone()[0]
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            return {
                "status": "online",
                "fts_documents": fts_count,
                "trigram_documents": trigram_count,
                "db_size_bytes": db_size,
                "db_path": self.db_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ─── Hybrid Search ────────────────────────────────────────────────────────

    def hybrid_search(
        self,
        query: str,
        n: int = 10,
        source_type: Optional[str] = None,
        keyword_weight: float = HYBRID_KEYWORD_WEIGHT,
        semantic_weight: float = HYBRID_SEMANTIC_WEIGHT,
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining FTS5 BM25 + ChromaDB cosine similarity.

        Args:
            query: Search query.
            n: Max results to return.
            source_type: Optional filter.
            keyword_weight: Weight for BM25 scores (default 0.6).
            semantic_weight: Weight for cosine scores (default 0.4).

        Returns:
            List of merged results sorted by combined score.
        """
        keyword_results = self.search(query, n=n * 3, source_type=source_type)

        semantic_results = self._chroma_search(query, n=n * 3, source_type=source_type)

        if not keyword_results and not semantic_results:
            return []

        norm_keyword = self._normalize_scores(keyword_results, "score", reverse=True)
        norm_semantic = self._normalize_scores(semantic_results, "distance", reverse=False)

        combined = self._merge_results(norm_keyword, norm_semantic, keyword_weight, semantic_weight)

        combined.sort(key=lambda x: x["hybrid_score"], reverse=True)

        return combined[:n]

    def _chroma_search(
        self,
        query: str,
        n: int = 10,
        source_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query ChromaDB for semantic search. Falls back to direct client if brain unavailable."""
        collection = None
        try:
            from core_agent.core.strike_brain import brain

            if brain and brain.memory and brain.memory._is_ready:
                collection = brain.memory._form_collection
        except Exception:
            pass

        if collection is None:
            try:
                import chromadb  # noqa: F811
                from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
                chroma_dir = os.getenv("CHROMA_DIR", "data/chroma")
                client = chromadb.PersistentClient(path=chroma_dir)
                collection = client.get_collection(
                    "form_insights", embedding_function=DefaultEmbeddingFunction()
                )
            except Exception as e:
                logger.debug(f"Direct ChromaDB client failed: {e}")
                return []

        try:
            where = {"type": source_type} if source_type else None
            results = collection.query(
                query_texts=[query], n_results=n, where=where, include=["documents", "metadatas", "distances"]
            )
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            return [
                {
                    "content": doc,
                    "metadata": meta,
                    "source_type": meta.get("type", "form_insight") if meta else "form_insight",
                    "distance": dist,
                    "method": "semantic",
                }
                for doc, meta, dist in zip(docs, metas, distances)
            ]
        except Exception as e:
            logger.debug(f"ChromaDB search failed: {e}")
            return []

    @staticmethod
    def _normalize_scores(
        results: List[Dict[str, Any]],
        score_key: str,
        reverse: bool = True,
    ) -> List[Dict[str, Any]]:
        """Min-max normalize scores to [0, 1].

        Args:
            results: List of result dicts.
            score_key: Key to normalize ('score' for BM25, 'distance' for cosine).
            reverse: True if lower raw score = better (BM25), False if higher = better (cosine similarity).

        Returns:
            Results with added 'normalized_score' in [0, 1].
        """
        if not results:
            return []

        raw_scores = [r.get(score_key, 0) for r in results]
        min_score = min(raw_scores)
        max_score = max(raw_scores)

        if max_score == min_score:
            for r in results:
                r["normalized_score"] = 1.0
            return results

        normalized = []
        for r in results:
            raw = r.get(score_key, 0)
            norm = (raw - min_score) / (max_score - min_score)
            if reverse:
                norm = 1.0 - norm
            nr = r.copy()
            nr["normalized_score"] = round(norm, 4)
            normalized.append(nr)
        return normalized

    def _merge_results(
        self,
        keyword_results: List[Dict[str, Any]],
        semantic_results: List[Dict[str, Any]],
        kw_weight: float,
        sem_weight: float,
    ) -> List[Dict[str, Any]]:
        """Merge and deduplicate results from both sources."""
        seen = {}
        all_results = []

        for r in keyword_results:
            content = r.get("content", "")
            h = hash(content[:500])
            if h not in seen:
                seen[h] = len(all_results)
                all_results.append({
                    "content": content,
                    "metadata": r.get("metadata", {}),
                    "source_type": r.get("source_type"),
                    "keyword_score": r.get("normalized_score", 0),
                    "semantic_score": 0.0,
                    "method": r.get("method", "bm25"),
                })
            else:
                idx = seen[h]
                all_results[idx]["keyword_score"] = max(
                    all_results[idx]["keyword_score"], r.get("normalized_score", 0)
                )
                all_results[idx]["method"] = r.get("method", "bm25")

        for r in semantic_results:
            content = r.get("content", "")
            h = hash(content[:500])
            if h not in seen:
                seen[h] = len(all_results)
                all_results.append({
                    "content": content,
                    "metadata": r.get("metadata", {}),
                    "source_type": r.get("source_type"),
                    "keyword_score": 0.0,
                    "semantic_score": r.get("normalized_score", 0),
                    "method": r.get("method", "semantic"),
                })
            else:
                idx = seen[h]
                all_results[idx]["semantic_score"] = max(
                    all_results[idx]["semantic_score"], r.get("normalized_score", 0)
                )
                if all_results[idx]["method"] == "bm25":
                    all_results[idx]["method"] = "hybrid"

        for r in all_results:
            r["hybrid_score"] = round(
                kw_weight * r["keyword_score"] + sem_weight * r["semantic_score"], 4
            )

        return all_results
