import numpy as np
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.emotion_service import EmotionService

_FAKE_IMAGE = np.zeros((100, 100, 3), dtype=np.uint8)


async def test_analyze_returns_nervousness_and_confidence_scores():
    service = EmotionService()
    fake_result = MagicMock()
    fake_result.multi_face_landmarks = [MagicMock()]
    with patch.object(service, '_decode_frame', return_value=_FAKE_IMAGE):
        with patch.object(service, '_run_facemesh', return_value=fake_result):
            with patch.object(service, '_landmarks_to_emotion', return_value="nervous"):
                with patch.object(service, '_landmarks_to_scores', return_value=(0.8, 0.2)):
                    with patch.object(service, '_landmarks_to_gaze', return_value="center"):
                        result = await service.analyze_frame(frame_b64="fake")

    assert "nervousness_score" in result
    assert "confidence_score" in result
    assert result["nervousness_score"] == 0.8
    assert result["confidence_score"] == 0.2


async def test_analyze_returns_gaze_direction():
    service = EmotionService()
    fake_result = MagicMock()
    fake_result.multi_face_landmarks = [MagicMock()]
    with patch.object(service, '_decode_frame', return_value=_FAKE_IMAGE):
        with patch.object(service, '_run_facemesh', return_value=fake_result):
            with patch.object(service, '_landmarks_to_emotion', return_value="neutral"):
                with patch.object(service, '_landmarks_to_scores', return_value=(0.3, 0.6)):
                    with patch.object(service, '_landmarks_to_gaze', return_value="left"):
                        result = await service.analyze_frame(frame_b64="fake")

    assert result["gaze_direction"] in ("center", "left", "right", "up", "down")
    assert result["gaze_direction"] == "left"


async def test_analyze_no_face_returns_full_defaults():
    service = EmotionService()
    fake_result = MagicMock()
    fake_result.multi_face_landmarks = None
    with patch.object(service, '_decode_frame', return_value=_FAKE_IMAGE):
        with patch.object(service, '_run_facemesh', return_value=fake_result):
            result = await service.analyze_frame(frame_b64="fake")

    assert result["emotion"] == "neutral"
    assert result["gaze_direction"] == "center"
    assert result["nervousness_score"] == 0.5
    assert result["confidence_score"] == 0.5


async def test_transcribe_returns_language_detection():
    from app.services.speech_service import SpeechService
    service = SpeechService()
    mock_transcript = MagicMock()
    mock_transcript.text = "Tell me about distributed systems."
    mock_transcript.language = "en"

    with patch.object(service._openai_client.audio.transcriptions, 'create',
                      new=AsyncMock(return_value=mock_transcript)):
        result = await service.transcribe_with_language(audio_bytes=b"fake_audio")

    assert result["transcript"] == "Tell me about distributed systems."
    assert result["detected_language"] == "en"
