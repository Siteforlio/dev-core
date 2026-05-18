import logging
from app.services.cluely.rag_service import RagService
from app.core.config import settings

logger = logging.getLogger(__name__)

class FilesystemService:
    def __init__(self):
        self._rag = RagService(index_dir=settings.devcore_file_index_path)
        self._root: str | None = None  # single project root for Semble

    def set_project_root(self, root: str) -> None:
        """Set the project root to index. Called when a live session starts."""
        self._root = root

    # kept for backwards compat — existing callers pass a dirs list
    def set_directories(self, dirs: list[str]) -> None:
        if dirs:
            self._root = dirs[0]

    async def build_index(self) -> None:
        if not self._root:
            logger.warning("[filesystem] No project root set — skipping index build")
            return
        await self._rag.build_index([self._root])

    async def search(self, query: str, k: int = 5) -> list[str]:
        return await self._rag.retrieve(query, k=k)
