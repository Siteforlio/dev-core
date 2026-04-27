import httpx, logging
from app.core.config import settings
from app.core.exceptions import CodeRunnerError

logger = logging.getLogger(__name__)

JUDGE0_URL = "https://judge0-ce.p.rapidapi.com/submissions"
LANGUAGE_IDS = {
    "python": 71, "javascript": 63, "typescript": 74,
    "java": 62, "cpp": 54, "go": 60, "rust": 73,
}

class CodeRunner:
    async def execute(self, code: str, language: str) -> dict:
        if not settings.judge0_api_key:
            raise CodeRunnerError(
                code="CODE_RUNNER_UNAVAILABLE",
                message="Code execution unavailable — no JUDGE0_API_KEY configured."
            )
        lang_id = LANGUAGE_IDS.get(language.lower())
        if lang_id is None:
            raise CodeRunnerError(message=f"Unsupported language: {language}")
        headers = {
            "X-RapidAPI-Key": settings.judge0_api_key,
            "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com",
        }
        payload = {"source_code": code, "language_id": lang_id, "stdin": ""}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{JUDGE0_URL}?wait=true", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            return {
                "output": data.get("stdout") or data.get("stderr") or "",
                "language": language,
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise CodeRunnerError(
                    code="CODE_RUNNER_QUOTA_EXCEEDED",
                    message="Daily code execution limit reached. Solution shown without running."
                )
            raise CodeRunnerError(message=str(e))
