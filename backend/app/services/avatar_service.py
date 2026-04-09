import httpx
from app.core.config import settings

SIMLI_API_BASE = "https://api.simli.ai"


class AvatarService:
    async def _call_simli_api(self, endpoint: str, payload: dict) -> dict:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{SIMLI_API_BASE}{endpoint}",
                json=payload,
                headers={"x-simli-api-key": settings.simli_api_key},
                timeout=10.0,
            )
            res.raise_for_status()
            return res.json()

    async def create_streaming_session(self, persona_description: str) -> dict:
        return await self._call_simli_api("/startE2ESession", {
            "apiKey": settings.simli_api_key,
            "faceId": "default",
            "systemPrompt": persona_description,
        })

    async def _send_audio_to_session(self, session_id: str, audio_bytes: bytes):
        # Audio bytes forwarded to Simli via the WebSocket layer
        pass

    async def send_audio(self, session_id: str, audio_bytes: bytes):
        await self._send_audio_to_session(session_id, audio_bytes)
