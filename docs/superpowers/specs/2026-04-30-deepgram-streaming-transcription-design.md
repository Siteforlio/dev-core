# Design: Deepgram Streaming Transcription

**Date:** 2026-04-30  
**Status:** Approved  
**Scope:** Replace `AudioService` (faster-whisper) with Deepgram Nova-2 live streaming in the Cluely overlay backend.

---

## Problem

The existing faster-whisper `small` model on a CPU-only Intel Iris Plus laptop produces ~3–5s transcription latency per chunk. The overlay session buffers 1500ms of audio before running inference, meaning end-to-end latency is 4–7s. This makes the transcript feel laggy and delays AI suggestion triggers.

---

## Solution

Replace local Whisper inference with **Deepgram Nova-2 live streaming**. Audio is forwarded in real-time to Deepgram's API; transcripts return in ~1–2s (faster than Whisper, though not sub-second due to the 1500ms chunking architecture on the Electron side). The Electron audio pipeline is unchanged — it already produces 16kHz mono PCM which is exactly what Deepgram expects.

---

## Architecture

```
Electron audio pipeline (unchanged)
  └─ binary frame [streamId (1B) + seq (2B) + PCM]
       └─ streamId=0x01 (mic)    → DeepgramTranscriber("user")
       └─ streamId=0x02 (system) → DeepgramTranscriber("interviewer")
                                         ↓
                     transcript callback (bridged via run_coroutine_threadsafe)
                                         ↓
                              WebSocket → frontend
```

Each overlay **session** owns two `DeepgramTranscriber` instances created on `session_start` and closed on `session_end` / disconnect. Transcriber references live in the local `session_ctx` dict inside each `handle()` call — never on `self` — matching the existing per-session keying pattern used by `_recent_texts`, `_suggestion_cache`, etc.

---

## Components

### `parse_audio_frame` — moved to `deepgram_service.py`

`parse_audio_frame` is a pure binary-frame utility with no Whisper dependency. It moves from `audio_service.py` to `deepgram_service.py`. `overlay_service.py` import line changes from:

```python
from app.services.cluely.audio_service import AudioService, parse_audio_frame
```
to:
```python
from app.services.cluely.deepgram_service import DeepgramTranscriber, parse_audio_frame
```

### `DeepgramTranscriber` (`backend/app/services/cluely/deepgram_service.py`)

Wraps a single Deepgram live connection for one audio stream.

**Responsibilities:**
- Open / close the Deepgram WebSocket connection using `deepgram-sdk>=3.0.0`
- Accept raw PCM bytes via `async def send(pcm: bytes)`
- Bridge transcript callbacks back to the FastAPI asyncio loop via `asyncio.run_coroutine_threadsafe(coro, loop)` — the Deepgram SDK v3 fires event handlers from its own internal thread, not from FastAPI's event loop
- Reconnect once automatically on unexpected disconnect; drop in-flight audio frames silently during the reconnection window
- Expose `async def close()` for clean teardown

**Deepgram options:**
| Parameter | Value | Reason |
|---|---|---|
| `model` | `nova-2` | Best accuracy on free tier |
| `language` | `en` | English-only interview context |
| `encoding` | `linear16` | Matches our PCM format |
| `sample_rate` | `16000` | Matches our resampled output |
| `channels` | `1` | Mono after stereo downmix |
| `smart_format` | `True` | Punctuation + capitalisation |
| `interim_results` | `True` | Partial transcripts for responsiveness |
| `utterance_end_ms` | `1000` | Finalise after 1s silence |
| `vad_events` | `True` | Speech start/end events |
| `endpointing` | `300` | ms before endpoint declared |
| `keepalive` | `True` | Prevent idle timeout |

**Thread bridging pattern:**
```python
loop = asyncio.get_event_loop()  # captured at session start

def _on_transcript(self, result, **kwargs):
    text = result.channel.alternatives[0].transcript
    if not result.is_final or not text:
        return
    asyncio.run_coroutine_threadsafe(
        self._callback(self._speaker, text),
        self._loop
    )
```

### `OverlayService` (modified)

**`_start_session`:**
1. Capture `loop = asyncio.get_event_loop()`
2. Create `mic_t = DeepgramTranscriber("user", api_key, loop, on_transcript_cb)`
3. Create `sys_t = DeepgramTranscriber("interviewer", api_key, loop, on_transcript_cb)`
4. `await mic_t.start()` and `await sys_t.start()`
5. Store both in `session_ctx["mic_transcriber"]` and `session_ctx["sys_transcriber"]`

**`_handle_audio`:** Routes parsed PCM to the correct transcriber. No inference call. No RMS check (Deepgram VAD handles silence internally).

```python
stream, seq, pcm = parse_audio_frame(raw)
key = "mic_transcriber" if stream == "mic" else "sys_transcriber"
t = session_ctx.get(key)
if t:
    await t.send(pcm)
```

**`on_transcript_cb`:** The async callback fired by `run_coroutine_threadsafe`. Contains the existing dedup logic, `ctx_mgr.push_transcript`, `ws.send_json`, and BERT trigger — identical to the logic currently in `_handle_audio` after the transcription result.

**Session teardown** (in `finally` block of `handle()`):
1. Set a flag so `send()` calls become no-ops immediately
2. `await mic_t.close()` then `await sys_t.close()` — both are coroutines
3. Then close the WebSocket (existing behaviour)

The `_safe_send` guard in the callback handles the case where the WebSocket closes before a final transcript callback fires.

**Side effect of removing `AudioService` import:** The Whisper preload daemon thread (started on import in `audio_service.py` line 51) will no longer fire once the import is removed. This is intentional and desirable — no model is loaded at startup.

### `AudioService` (deleted)

`audio_service.py` is deleted after Deepgram is verified working end-to-end.

---

## Configuration

```env
DEEPGRAM_API_KEY=<key from console.deepgram.com>
```

Loaded via `app/core/config.py` (existing settings pattern). If the key is missing or empty, `_start_session` sends an `error` frame to the client and returns without creating transcribers, so the session runs without transcription rather than crashing.

---

## Dependencies

Add to `backend/requirements.txt`:
```
deepgram-sdk>=3.0.0
```

Remove from environment (may be ad-hoc installed, not in requirements.txt):
```
faster-whisper
numpy  # only if no other service uses it
```

---

## Files Changed

| File | Action |
|---|---|
| `backend/app/services/cluely/deepgram_service.py` | **Create** — `DeepgramTranscriber` + `parse_audio_frame` |
| `backend/app/services/cluely/overlay_service.py` | **Modify** — session lifecycle, audio routing, transcript callback |
| `backend/app/services/cluely/audio_service.py` | **Delete** after verification |
| `backend/requirements.txt` | **Modify** — add deepgram-sdk |
| `.env` / `.env.example` | **Create/modify** — add DEEPGRAM_API_KEY |

Electron, frontend, WebSocket protocol: **unchanged**.

---

## Out of Scope

- System audio loopback device setup (separate issue)
- Speaker diarization within a single stream
- Deepgram keyword boosting / custom vocabulary
