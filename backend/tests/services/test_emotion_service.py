import numpy as np
from unittest.mock import patch, MagicMock
from app.services.emotion_service import EmotionService

_FAKE_IMAGE = np.zeros((100, 100, 3), dtype=np.uint8)


async def test_analyze_returns_emotion_state():
    service = EmotionService()
    fake_result = MagicMock()
    fake_result.multi_face_landmarks = [MagicMock()]
    with patch.object(service, '_decode_frame', return_value=_FAKE_IMAGE):
        with patch.object(service, '_run_facemesh', return_value=fake_result):
            with patch.object(service, '_landmarks_to_emotion', return_value="confident"):
                with patch.object(service, '_landmarks_to_scores', return_value=(0.2, 0.85)):
                    with patch.object(service, '_landmarks_to_gaze', return_value="center"):
                        result = await service.analyze_frame(frame_b64="fake_base64_data")
    assert result["emotion"] == "confident"


async def test_analyze_returns_neutral_when_no_face():
    service = EmotionService()
    fake_result = MagicMock()
    fake_result.multi_face_landmarks = None
    with patch.object(service, '_decode_frame', return_value=_FAKE_IMAGE):
        with patch.object(service, '_run_facemesh', return_value=fake_result):
            result = await service.analyze_frame(frame_b64="fake_base64_data")
    assert result["emotion"] == "neutral"
    assert result["eye_contact"] is False
