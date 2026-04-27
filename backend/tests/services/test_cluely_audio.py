import pytest
import struct
from unittest.mock import AsyncMock, patch
from app.services.cluely.audio_service import AudioService, parse_audio_frame, detect_silence

def test_parse_audio_frame_mic():
    # 3-byte header: stream_id=0x01, chunk_seq=1 (big-endian uint16)
    pcm = b'\x00\x01' * 100
    frame = struct.pack('!BH', 0x01, 1) + pcm
    stream_id, seq, data = parse_audio_frame(frame)
    assert stream_id == 'mic'
    assert seq == 1
    assert data == pcm

def test_parse_audio_frame_system():
    pcm = b'\x00\x02' * 50
    frame = struct.pack('!BH', 0x02, 42) + pcm
    stream_id, seq, data = parse_audio_frame(frame)
    assert stream_id == 'system'
    assert seq == 42

def test_detect_silence_on_quiet_buffer():
    # Near-zero PCM → silence
    silent = (b'\x00\x00' * 8000)  # 0.5s at 16kHz
    assert detect_silence(silent) is True

def test_detect_silence_on_loud_buffer():
    import struct as st
    loud = st.pack('<' + 'h' * 8000, *([20000] * 8000))
    assert detect_silence(loud) is False

@pytest.mark.asyncio
async def test_transcribe_labels_speaker():
    import app.services.cluely.audio_service as audio_mod
    audio_mod._whisper_model = None  # reset singleton so mock.load_model is called
    svc = AudioService()
    pcm = b'\x00\x00' * 16000  # 1s of silence
    with patch('app.services.cluely.audio_service.whisper') as mock_w:
        mock_w.load_model.return_value.transcribe.return_value = {'text': 'hello'}
        result = await svc.transcribe(pcm, speaker='interviewer')
    assert result['speaker'] == 'interviewer'
    assert result['text'] == 'hello'
