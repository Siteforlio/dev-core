import asyncio, json, os, logging
from pathlib import Path

logger = logging.getLogger(__name__)
CHUNK_SIZE = 400  # characters


class RagService:
    def __init__(self, index_dir: str = "~/.devcore/file_index"):
        self._index_dir = Path(index_dir).expanduser()
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self._index_dir / "index_meta.json"
        self._chunks: list[str] = []
        self._embeddings = None
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

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
                        new_chunk_cache[fpath] = chunk_cache[fpath]  # carry forward
                    else:
                        text = self._read_file(fpath)
                        new_chunk_cache[fpath] = self._chunk_text(text)
                        changed = True

        # Check for removed files
        if set(new_meta.keys()) != set(meta.keys()):
            changed = True

        all_chunks = [c for chunks in new_chunk_cache.values() for c in chunks]

        if not changed and self._embeddings is not None:
            return  # nothing changed, embeddings still valid

        model = self._get_model()
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
        model = self._get_model()
        q_emb = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        scores = (self._embeddings @ q_emb.T).squeeze()
        top_k = int(min(k, len(self._chunks)))
        indices = scores.argsort()[-top_k:][::-1]
        return [self._chunks[i] for i in indices]
