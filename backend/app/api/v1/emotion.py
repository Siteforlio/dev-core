from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.core.security import decode_token
from app.services.emotion_service import EmotionService

router = APIRouter(prefix="/emotion", tags=["emotion"])
_bearer = HTTPBearer(auto_error=True)


def _require_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    return decode_token(credentials.credentials)


class FrameRequest(BaseModel):
    frame_b64: str


@router.post("/analyze-frame")
async def analyze_frame(body: FrameRequest, _user_id: str = Depends(_require_user)):
    service = EmotionService()
    result = await service.analyze_frame(frame_b64=body.frame_b64)
    return {"data": result, "error": None}
