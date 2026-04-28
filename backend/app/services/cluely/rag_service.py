import asyncio, json, os, logging, threading
from pathlib import Path

logger = logging.getLogger(__name__)
CHUNK_SIZE = 400          # characters per chunk
SIMILARITY_THRESHOLD = 0.7  # minimum cosine similarity to include a chunk
MAX_CHUNKS = 2            # never return more than 2 chunks — keeps prompt tokens lean

# ---------------------------------------------------------------------------
# Global singleton for the embedding model — same pattern as Whisper in
# audio_service.py (ARCHITECTURE.md §4.5).  Prevents 500ms+ reload penalty
# when RagService is re-instantiated across sessions.
# ---------------------------------------------------------------------------
_embedding_model = None
_embedding_lock = threading.Lock()


def _get_model():
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                from sentence_transformers import SentenceTransformer
                _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


class RagService:
    def __init__(self, index_dir: str = "~/.devcore/file_index"):
        self._index_dir = Path(index_dir).expanduser()
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self._index_dir / "index_meta.json"
        self._chunks: list[str] = []
        self._embeddings = None

    def _chunk_text(self, text: str) -> list[str]:
        return [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE) if text[i:i+CHUNK_SIZE].strip()]

    def _read_file(self, path: str) -> str:
        try:
            if path.endswith(".pdf"):
                import pdfminer.high_level
                return pdfminer.high_level.extract_text(path)
            elif path.endswith(".docx"):
                import docx
                doc = docx.Document(path)
                return "\n".join(p.text for p in doc.paragraphs)
            with open(path, encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning("Could not read %s: %s", path, e)
            return ""

    async def build_index(self, directories: list[str]) -> None:
        await asyncio.to_thread(self._build_sync, directories)

    def _build_sync(self, directories: list[str]) -> None:
        chunks_path = self._index_dir / "index_chunks.json"
        meta = json.loads(self._meta_path.read_text()) if self._meta_path.exists() else {}
        chunk_cache: dict[str, list[str]] = json.loads(chunks_path.read_text()) if chunks_path.exists() else {}

        new_meta: dict[str, float] = {}
        new_chunk_cache: dict[str, list[str]] = {}
        changed = False

        for d in directories:
            for root, _, files in os.walk(os.path.expanduser(d)):
                for fname in files:
                    if not fname.endswith((".txt", ".pdf", ".md", ".docx")):
                        continue
                    fpath = os.path.join(root, fname)
                    mtime = os.path.getmtime(fpath)
                    new_meta[fpath] = mtime
                    if meta.get(fpath) == mtime and fpath in chunk_cache:
                        new_chunk_cache[fpath] = chunk_cache[fpath]
                    else:
                        text = self._read_file(fpath)
                        new_chunk_cache[fpath] = self._chunk_text(text)
                        changed = True

        if set(new_meta.keys()) != set(meta.keys()):
            changed = True

        all_chunks = [c for chunks in new_chunk_cache.values() for c in chunks]

        if not changed and self._embeddings is not None:
            return

        model = _get_model()
        self._chunks = all_chunks
        self._embeddings = model.encode(all_chunks, convert_to_numpy=True, normalize_embeddings=True) if all_chunks else None
        self._meta_path.write_text(json.dumps(new_meta))
        chunks_path.write_text(json.dumps(new_chunk_cache))
        logger.info("RAG index built: %d chunks", len(all_chunks))

    async def retrieve(self, query: str, k: int = 3) -> list[str]:
        if self._embeddings is None or len(self._chunks) == 0:
            return []
        return await asyncio.to_thread(self._retrieve_sync, query, k)

    def _retrieve_sync(self, query: str, k: int) -> list[str]:
        model = _get_model()
        q_emb = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        scores = (self._embeddings @ q_emb.T).squeeze()
        # Apply similarity threshold and cap at MAX_CHUNKS — keeps prompt lean
        # and avoids injecting low-relevance noise into the LLM context.
        cap = min(k, MAX_CHUNKS, len(self._chunks))
        indices = scores.argsort()[-cap:][::-1]
        return [self._chunks[i] for i in indices if scores[i] >= SIMILARITY_THRESHOLD]
