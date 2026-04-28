import httpx, logging
from app.core.config import settings

logger = logging.getLogger(__name__)
SERP_URL = "https://serpapi.com/search"

class SearchService:
    async def search(self, query: str, num: int = 3) -> list[str]:
        if not settings.serp_api_key:
            return ["[Search unavailable — no SERP_API_KEY configured]"]
        params = {"q": query, "api_key": settings.serp_api_key, "num": num}
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(SERP_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        return [r.get("snippet", "") for r in data.get("organic_results", [])[:num]]
