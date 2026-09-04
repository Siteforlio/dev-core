import io
import struct
import time
import wave
import logging
import asyncio
from typing import Literal, Callable, Awaitable

from deepgram import AsyncDeepgramClient

logger = logging.getLogger(__name__)

_np = None


def _get_np():
    global _np
    if _np is None:
        import numpy as np
        _np = np
    return _np


MIN_SAMPLES = 1600    # 100 ms at 16 kHz — drop frames shorter than this
MIC_GAIN    = 4.0     # software boost for quiet mic devices

_HALLUCINATIONS = {
    "", ".", "..", "...", " ", "you", "you.", "thank you", "thank you.",
    "thanks.", "thanks for watching.", "bye.", "bye bye.", "goodbye.",
    "ok.", "okay.", "and", "and.", "um", "um.", "uh", "uh.", "so", "so.",
    "i", "i.", "the", "the.", "mm-hmm.", "mm-hmm", "hmm.", "hmm",
}

_HALLUCINATION_FRAGMENTS = [
    "please don't forget to subscribe",
    "don't forget to subscribe",
    "subscribe if you like",
    "thanks for watching",
    "like and subscribe",
    "see you next time",
    "have a great day",
    "www.",
    "http",
    "subtitles by",
    "transcribed by",
    "amara.org",
]

_client: AsyncDeepgramClient | None = None
_client_key: str = ""


def _get_client(api_key: str) -> AsyncDeepgramClient:
    global _client, _client_key
    if _client is None or _client_key != api_key:
        _client = AsyncDeepgramClient(api_key=api_key)
        _client_key = api_key
    return _client


def parse_audio_frame(data: bytes) -> tuple[Literal["mic", "system"], int, bytes]:
    if len(data) < 3:
        raise ValueError("Frame too short")
    stream_id_byte, seq = struct.unpack_from('!BH', data, 0)
    pcm = data[3:]
    stream: Literal["mic", "system"] = "mic" if stream_id_byte == 0x01 else "system"
    return stream, seq, pcm


def _rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    np = _get_np()
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(samples ** 2))) / 32768.0


def _boost(pcm: bytes, gain: float) -> bytes:
    np = _get_np()
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    arr = np.clip(arr * gain, -32768, 32767).astype(np.int16)
    return arr.tobytes()


def detect_silence(pcm: bytes) -> bool:
    return _rms(pcm) < 0.008


def _pcm_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _filter_hallucination(text: str) -> str:
    tl = text.lower()
    if tl in _HALLUCINATIONS:
        return ""
    if any(f in tl for f in _HALLUCINATION_FRAGMENTS):
        return ""
    return text


class AudioService:
    """
    Transcription via Deepgram nova-2 pre-recorded API.

    Per-utterance HTTP call — ~100-200ms latency, no rate limit issues,
    $200 free credits (~700 hours) on signup.
    """

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def transcribe(self, pcm: bytes, speaker: Literal["interviewer", "user"]) -> dict:
        t_total = time.perf_counter()

        if len(pcm) < MIN_SAMPLES * 2:
            logger.debug("[audio] DROP short frame %d bytes | %s", len(pcm), speaker)
            return {"speaker": speaker, "text": "", "words": [], "timings": {}}

        if speaker == "user":
            pcm = _boost(pcm, MIC_GAIN)

        rms = _rms(pcm)
        logger.info("[audio] frame %d bytes | rms=%.4f | %s", len(pcm), rms, speaker)

        if rms < 0.004:
            return {"speaker": speaker, "text": "", "words": [], "timings": {}}

        wav_bytes = _pcm_to_wav(pcm)

        try:
            t_infer = time.perf_counter()
            response = await _get_client(self._api_key).listen.v1.media.transcribe_file(
                request=wav_bytes,
                model="nova-2",
                language="en",
                smart_format=True,
                punctuate=True,
            )
            infer_ms = round((time.perf_counter() - t_infer) * 1000, 1)

            alt = response.results.channels[0].alternatives[0]
            text = (alt.transcript or "").strip()
            raw_words = [w.word for w in (alt.words or []) if w.word and w.word.strip()]
        except Exception as e:
            logger.error("[audio] Deepgram transcription error: %s", e)
            return {"speaker": speaker, "text": "", "words": [], "timings": {}}

        text  = _filter_hallucination(text)
        words = [w for w in raw_words if _filter_hallucination(w)]

        total_ms = round((time.perf_counter() - t_total) * 1000, 1)
        logger.info("[audio] %s | rms=%.4f | infer=%.0fms | total=%.0fms | %r",
                    speaker, rms, infer_ms, total_ms, text[:80])

        return {"speaker": speaker, "text": text, "words": words,
                "timings": {"infer_ms": infer_ms, "total_ms": total_ms}}


class StreamingAudioSession:
    """
    Deepgram streaming session — open once per interview session, pipe raw
    PCM frames in real-time, get words back as they are spoken (~100ms latency).

    Usage:
        session = StreamingAudioSession(on_word=..., on_utterance=...)
        await session.start()
        await session.send(pcm_bytes, speaker="user")
        await session.stop()
    """

    def __init__(
        self,
        on_word: Callable[[str, str], Awaitable[None]],       # (word, speaker)
        on_utterance: Callable[[str, str], Awaitable[None]],  # (full_text, speaker)
        api_key: str = "",
    ):
        self._on_word      = on_word
        self._on_utterance = on_utterance
        self._api_key      = api_key
        self._conn         = None
        self._speaker      = "interviewer"
        self._running      = False

    async def start(self):
        client = _get_client(self._api_key)
        self._conn = await client.listen.v1.connect(
            model="nova-2",
            language="en",
            smart_format=True,
            punctuate=True,
            interim_results=True,
            utterance_end_ms=1000,
            vad_events=True,
            encoding="linear16",
            sample_rate=16000,
            channels=1,
        )
        self._running = True

        async def _on_message(result):
            try:
                channel = result.channel
                alt     = channel.alternatives[0]
                words   = [w.word for w in (alt.words or []) if w.word and w.word.strip()]
                text    = (alt.transcript or "").strip()
                is_final = result.is_final

                if words and not is_final:
                    # Interim — emit words one by one for console display
                    for w in words:
                        await self._on_word(w, self._speaker)
                elif text and is_final:
                    text = _filter_hallucination(text)
                    if text:
                        await self._on_utterance(text, self._speaker)
            except Exception as e:
                logger.debug("[streaming] message parse error: %s", e)

        self._conn.on("Results", _on_message)
        await self._conn.start()
        logger.info("[audio] Deepgram streaming session started")

    async def send(self, pcm: bytes, speaker: Literal["interviewer", "user"]):
        if not self._conn or not self._running:
            return
        self._speaker = speaker
        if speaker == "user":
            pcm = _boost(pcm, MIC_GAIN)
        rms = _rms(pcm)
        if rms < 0.004:
            return
        try:
            await self._conn.send(pcm)
        except Exception as e:
            logger.error("[audio] streaming send error: %s", e)

    async def stop(self):
        self._running = False
        if self._conn:
            try:
                await self._conn.finish()
            except Exception:
                pass
            self._conn = None
        logger.info("[audio] Deepgram streaming session stopped")
