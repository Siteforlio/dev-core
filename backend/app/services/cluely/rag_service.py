import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RagService:
    """
    Code-aware semantic search powered by Semble.

    Semble uses a hybrid retrieval strategy:
      - Static embeddings (Model2Vec / potion-code-16M) for semantic similarity
      - BM25 lexical matching for identifier / API name searches
      - Reciprocal Rank Fusion (RRF) to combine both scores
      - Definition boosting, identifier stem matching, file coherence scoring

    Replaces the previous sentence-transformers + cosine-similarity approach,
    which only indexed .txt/.pdf/.md/.docx and missed all source code.
    """

    def __init__(self, index_dir: str = "~/.devcore/file_index"):
        # index_dir kept for API compatibility — Semble manages its own cache
        self._index_dir = Path(index_dir).expanduser()
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._index = None          # SembleIndex instance, built on demand
        self._indexed_path: str | None = None  # track what was last indexed

    # ------------------------------------------------------------------
    # Public API (mirrors the old RagService interface)
    # ------------------------------------------------------------------

    async def build_index(self, directories: list[str]) -> None:
        """Index all source files under the given directories."""
        await asyncio.to_thread(self._build_sync, directories)

    async def retrieve(self, query: str, k: int = 5) -> list[str]:
        """Return up to k relevant code snippets for the query."""
        if self._index is None:
            return []
        return await asyncio.to_thread(self._retrieve_sync, query, k)

    # ------------------------------------------------------------------
    # Sync internals (run in executor to avoid blocking the event loop)
    # ------------------------------------------------------------------

    def _build_sync(self, directories: list[str]) -> None:
        from semble import SembleIndex

        if not directories:
            logger.warning("[rag] No directories provided — index not built")
            return

        root = str(Path(directories[0]).expanduser().resolve())

        # Avoid re-indexing the same path
        if self._indexed_path == root and self._index is not None:
            logger.info("[rag] Index already up to date for %s", root)
            return

        logger.info("[rag] Building Semble index for %s …", root)
        try:
            self._index = SembleIndex.from_path(root)
            self._indexed_path = root
            logger.info("[rag] Semble index ready for %s", root)
        except Exception as e:
            logger.error("[rag] Semble indexing failed: %s", e)
            self._index = None

    def _retrieve_sync(self, query: str, k: int) -> list[str]:
        try:
            results = self._index.search(query, top_k=k)
            snippets = []
            for r in results:
                # Semble SearchResult: .chunk.file_path, .chunk.start_line, .chunk.content
                chunk = r.chunk
                path  = getattr(chunk, 'file_path', '')
                line  = getattr(chunk, 'start_line', None)
                text  = getattr(chunk, 'content', '') or ''
                loc   = f"{path}:{line}" if line else path
                snippets.append(f"// {loc}\n{text.strip()}")
            return snippets
        except Exception as e:
            logger.error("[rag] Semble search failed: %s", e)
            return []
