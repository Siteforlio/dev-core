from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import Response
from app.services.speech_service import SpeechService

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post("/synthesize")
async def synthesize(text: str = Form(...), language: str = Form(default="en")):
    service = SpeechService()
    audio_bytes = await service.synthesize(text=text, language=language)
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form(default="en"),
):
    service = SpeechService()
    audio_bytes = await audio.read()
    text = await service.transcribe(audio_bytes=audio_bytes, language_hint=language)
    return {"data": {"transcript": text}, "error": None}
