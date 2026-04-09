from unittest.mock import patch, MagicMock
from app.services.emotion_service import EmotionService


async def test_analyze_returns_emotion_state():
    service = EmotionService()
    fake_result = MagicMock()
    fake_result.multi_face_landmarks = [MagicMock()]
    with patch.object(service, '_run_facemesh', return_value=fake_result):
        with patch.object(service, '_landmarks_to_emotion', return_value="confident"):
            result = await service.analyze_frame(frame_b64="fake_base64_data")
    assert result["emotion"] in ("neutral", "confident", "nervous", "uncertain", "engaged")


async def test_analyze_returns_neutral_when_no_face():
    service = EmotionService()
    fake_result = MagicMock()
    fake_result.multi_face_landmarks = None
    with patch.object(service, '_run_facemesh', return_value=fake_result):
        result = await service.analyze_frame(frame_b64="fake_base64_data")
    assert result["emotion"] == "neutral"
    assert result["eye_contact"] is False
