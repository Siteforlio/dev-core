from fastapi import APIRouter
from pydantic import BaseModel
from app.services.emotion_service import EmotionService

router = APIRouter(prefix="/emotion", tags=["emotion"])


class FrameRequest(BaseModel):
    frame_b64: str


@router.post("/analyze-frame")
async def analyze_frame(body: FrameRequest):
    service = EmotionService()
    result = await service.analyze_frame(frame_b64=body.frame_b64)
    return {"data": result, "error": None}
