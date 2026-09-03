from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.services.speech_service import SpeechService
from app.services.api_keys_service import ApiKeysService

router = APIRouter(prefix="/speech", tags=["speech"])
_bearer = HTTPBearer(auto_error=False)
_bearer_strict = HTTPBearer(auto_error=True)


def _get_user_id(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str | None:
    if not credentials:
        return None
    try:
        return decode_token(credentials.credentials)
    except Exception:
        return None


def _require_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer_strict)) -> str:
    return decode_token(credentials.credentials)


@router.post("/synthesize")
async def synthesize(
    text: str = Form(...),
    language: str = Form(default="en"),
    _user_id: str = Depends(_require_user),
):
    service = SpeechService()
    audio_bytes = await service.synthesize(text=text, language=language)
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form(default="en"),
    user_id: str | None = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    deepgram_key: str | None = None
    if user_id:
        deepgram_key = await ApiKeysService(db).get_decrypted(user_id, "deepgram_api_key")
    service = SpeechService()
    audio_bytes = await audio.read()
    text = await service.transcribe(audio_bytes=audio_bytes, language_hint=language, api_key=deepgram_key)
    return {"data": {"transcript": text}, "error": None}
