import logging
from app.services.cluely.rag_service import RagService
from app.core.config import settings

logger = logging.getLogger(__name__)

class FilesystemService:
    def __init__(self):
        self._rag = RagService(index_dir=settings.devcore_file_index_path)
        self._dirs: list[str] = ["~/Documents", "~/Desktop"]

    def set_directories(self, dirs: list[str]) -> None:
        self._dirs = dirs

    async def build_index(self) -> None:
        await self._rag.build_index(self._dirs)

    async def search(self, query: str, k: int = 3) -> list[str]:
        return await self._rag.retrieve(query, k=k)
