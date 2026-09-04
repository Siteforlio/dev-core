import httpx, logging

logger = logging.getLogger(__name__)
SERP_URL = "https://serpapi.com/search"

class SearchService:
    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    async def search(self, query: str, num: int = 3) -> list[str]:
        if not self._api_key:
            return ["[Search unavailable — no SERP API key configured in Settings → API Keys]"]
        params = {"q": query, "api_key": self._api_key, "num": num}
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(SERP_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        return [r.get("snippet", "") for r in data.get("organic_results", [])[:num]]
