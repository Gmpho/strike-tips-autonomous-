"""
ChromaDB Racing Memory - Vector Store for Long-Term Intelligence
Stores race form insights and chat history for RAG grounding.
"""

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger("racing-memory")

try:
    import chromadb
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False


def _make_embedding_fn():
    """
    Returns the best available embedding function:
    1. embeddinggemma:300m via Ollama (local, free, already pulled)
    2. Gemini text-embedding-004 (cloud fallback)
    3. ChromaDB default all-MiniLM (last resort)
    """
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction, EmbeddingFunction
    from core_agent.config.model_config import ModelConfig
    import httpx

    class OllamaEmbeddingFn(EmbeddingFunction):
        def __call__(self, input: list) -> list:
            host = ModelConfig.OLLAMA_BASE_URL
            model = os.getenv("MODEL_EMBEDDER", "embeddinggemma:300m")
            results = []
            for text in input:
                try:
                    with httpx.Client(timeout=15.0) as client:
                        r = client.post(f"{host}/api/embeddings", json={"model": model, "prompt": text})
                        results.append(r.json().get("embedding", []))
                except Exception:
                    results.append([])
            return results

    # Try Ollama first
    try:
        fn = OllamaEmbeddingFn()
        # Quick health check
        test = fn(["test"])
        if test and test[0]:
            logger.info("[MEMORY] Embedding: embeddinggemma:300m (Ollama)")
            return fn
    except Exception:
        pass

    # Gemini fallback
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
            logger.info("[MEMORY] Embedding: Gemini text-embedding-004 (fallback)")
            return GoogleGenerativeAiEmbeddingFunction(api_key=gemini_key, model_name="models/text-embedding-004")
        except Exception:
            pass

    logger.info("[MEMORY] Embedding: ChromaDB default (last resort)")
    return DefaultEmbeddingFunction()


class RacingMemory:
    """
    Long-term vector memory for race intelligence and chat history.
    Backed by ChromaDB with the all-MiniLM-L6-v2 embedding model.

    Collections:
      - form_insights: Horse form data, track stats, official tips
      - chat_history: Conversation history for context
    """

    def __init__(self, data_dir: str = None):
        from core_agent.config.paths import CHROMA_DIR

        self.data_dir = os.path.abspath(data_dir or CHROMA_DIR)
        os.makedirs(self.data_dir, exist_ok=True)

        self._client = None
        self._form_collection = None
        self._chat_collection = None
        self._is_ready = False

        if HAS_CHROMA:
            self._init_chroma()

    def _init_chroma(self):
        """Initialize ChromaDB — cloud if CHROMA_API_KEY is set, else local persistent."""
        try:
            import chromadb

            chroma_api_key = os.getenv("CHROMA_API_KEY", "")
            chroma_host = os.getenv("CHROMA_HOST", "")
            chroma_tenant = os.getenv("CHROMA_TENANT", "")
            chroma_database = os.getenv("CHROMA_DATABASE", "default_database")

            # Build embedding function: Ollama local → Gemini fallback → ChromaDB default
            embed_fn = _make_embedding_fn()

            if chroma_api_key and chroma_host:
                # ChromaDB Cloud
                self._client = chromadb.HttpClient(
                    host=chroma_host,
                    ssl=True,
                    headers={"x-chroma-token": chroma_api_key},
                    tenant=chroma_tenant or chromadb.DEFAULT_TENANT,
                    database=chroma_database,
                )
                logger.info(f"[MEMORY] ChromaDB Cloud: {chroma_host}/{chroma_database}")
            else:
                self._client = chromadb.PersistentClient(path=self.data_dir)
                logger.info(f"[MEMORY] ChromaDB local: {self.data_dir}")

            col_kwargs = {"metadata": {"hnsw:space": "cosine"}, "embedding_function": embed_fn}
            self._form_collection = self._client.get_or_create_collection(
                name="form_insights", **col_kwargs
            )
            self._chat_collection = self._client.get_or_create_collection(
                name="chat_history", **col_kwargs
            )
            self._is_ready = True
            logger.info(f"[MEMORY] Ready — form:{self._form_collection.count()} chat:{self._chat_collection.count()}")
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}")
            self._is_ready = False

    # ─── Form Insights ────────────────────────────────────────────────────────

    def add_form_insight(
        self,
        horse: str,
        insight: str,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Store a form insight in the vector database"""
        if not self._is_ready:
            return False
        try:
            doc_id = f"{horse}_{hash(insight) % 100000}"
            self._form_collection.upsert(
                documents=[insight],
                ids=[doc_id],
                metadatas=[metadata or {}],
            )
            return True
        except Exception as e:
            logger.error(f"Memory write error: {e}")
            return False

    def search_form_insights(
        self, query: str, n_results: int = 5, where: Optional[Dict] = None
    ) -> List[Dict]:
        """Semantic search over stored form insights"""
        if not self._is_ready:
            return []
        try:
            kwargs = {"query_texts": [query], "n_results": n_results}
            if where:
                kwargs["where"] = where

            results = self._form_collection.query(**kwargs)
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            return [
                {"content": doc, "metadata": meta, "distance": dist}
                for doc, meta, dist in zip(docs, metas, distances)
            ]
        except Exception as e:
            logger.error(f"Memory search error: {e}")
            return []

    # ─── Chat History ─────────────────────────────────────────────────────────

    def add_chat_message(self, role: str, content: str, source: str = "web") -> bool:
        """Store a chat message in history"""
        if not self._is_ready:
            return False
        try:
            from datetime import datetime

            doc_id = f"chat_{datetime.now().timestamp()}"
            self._chat_collection.add(
                documents=[content],
                ids=[doc_id],
                metadatas=[{"role": role, "source": source, "ts": doc_id}],
            )
            return True
        except Exception as e:
            logger.error(f"Chat memory write error: {e}")
            return False

    def get_chat_history(self, limit: int = 20) -> List[Dict]:
        """Retrieve recent chat history"""
        if not self._is_ready:
            return []
        try:
            results = self._chat_collection.get(
                limit=limit,
                include=["documents", "metadatas"],
            )
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            return [
                {"content": doc, "role": meta.get("role", "user")}
                for doc, meta in zip(docs, metas)
            ]
        except Exception as e:
            logger.error(f"Chat history read error: {e}")
            return []

    def clear_chat_history(self, source: Optional[str] = None) -> bool:
        """Clear chat history, optionally filtered by source"""
        if not self._is_ready:
            return False
        try:
            if source:
                results = self._chat_collection.get(where={"source": source})
                ids = results.get("ids", [])
                if ids:
                    self._chat_collection.delete(ids=ids)
            else:
                self._client.delete_collection("chat_history")
                self._chat_collection = self._client.get_or_create_collection(
                    "chat_history"
                )
            return True
        except Exception as e:
            logger.error(f"Clear history error: {e}")
            return False

    def get_stats(self) -> Dict:
        """Return memory statistics"""
        if not self._is_ready:
            return {"status": "offline", "reason": "chromadb not available"}
        try:
            return {
                "status": "online",
                "form_insights": self._form_collection.count(),
                "chat_messages": self._chat_collection.count(),
                "data_dir": self.data_dir,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate a vector embedding for the given text using local Ollama.
        Uses the model defined in ModelConfig.EMBEDDER.
        """
        import httpx
        from core_agent.config.model_config import ModelConfig

        host = ModelConfig.OLLAMA_HOST or "http://localhost:11434"
        model = ModelConfig.EMBEDDER or "nomic-embed-text"

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{host}/api/embeddings", json={"model": model, "prompt": text}
                )
                if resp.status_code == 200:
                    return resp.json().get("embedding", [])
                else:
                    logger.error(f"Embedding failed: {resp.text}")
                    return []
        except Exception as e:
            logger.error(f"Ollama connection error during embedding: {e}")
            return []
