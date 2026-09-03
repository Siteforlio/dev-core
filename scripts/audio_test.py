"""
audio_test.py — DevCore audio diagnostic tool

VAD-based live transcription: accumulates audio while you speak,
flushes to Groq Whisper the moment you pause. Feels word-by-word.

Usage:
    python scripts/audio_test.py
"""

import os, sys, io, wave, time, threading, queue
import numpy as np

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    print("ERROR: Set GROQ_API_KEY environment variable before running this script.")
    sys.exit(1)
SAMPLE_RATE  = 16000
FRAME_MS     = 30       # VAD frame size in ms
FRAME_BYTES  = SAMPLE_RATE * FRAME_MS // 1000 * 2  # bytes per frame (int16 mono)

# VAD thresholds
SPEECH_RMS      = 0.004   # rms above this = speech
SILENCE_FRAMES  = 20      # consecutive silent frames before flush (~600ms)
MIN_SPEECH_MS   = 200     # ignore utterances shorter than this
MIC_GAIN        = 4.0

HALLUCINATIONS = {
    "", ".", "..", "...", " ", "you", "you.", "thank you", "thank you.",
    "thanks.", "thanks for watching.", "bye.", "bye bye.", "goodbye.",
    "ok.", "okay.", "and", "and.", "um", "um.", "uh", "uh.",
    "so", "so.", "i", "i.", "the", "the.",
}

try:
    import pyaudiowpatch as pyaudio
    HAS_WPATCH = True
except ImportError:
    import pyaudio
    HAS_WPATCH = False

pa = pyaudio.PyAudio()


# ── Audio helpers ──────────────────────────────────────────────────────────

def frame_rms(pcm: bytes) -> float:
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(arr ** 2))) / 32768.0


def boost(pcm: bytes, gain: float) -> bytes:
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    return np.clip(arr * gain, -32768, 32767).astype(np.int16).tobytes()


def stereo_to_mono(buf: bytes) -> bytes:
    arr = np.frombuffer(buf, dtype=np.int16).reshape(-1, 2)
    return ((arr[:, 0].astype(np.int32) + arr[:, 1]) // 2).astype(np.int16).tobytes()


def resample_to_16k(buf: bytes, from_rate: int) -> bytes:
    if from_rate == SAMPLE_RATE:
        return buf
    arr = np.frombuffer(buf, dtype=np.int16)
    ratio = from_rate / SAMPLE_RATE
    idx = (np.arange(int(len(arr) / ratio)) * ratio).astype(int).clip(0, len(arr) - 1)
    return arr[idx].astype(np.int16).tobytes()


def to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()


# ── Transcription ──────────────────────────────────────────────────────────

def transcribe(wav_bytes: bytes, client) -> str:
    try:
        result = client.audio.transcriptions.create(
            file=("audio.wav", wav_bytes, "audio/wav"),
            model="whisper-large-v3-turbo",
            language="en",
            response_format="text",
        )
        text = result.strip() if isinstance(result, str) else ""
        return "" if text.lower() in HALLUCINATIONS else text
    except Exception as e:
        return f"[error: {e}]"


# ── Device listing ─────────────────────────────────────────────────────────

def get_devices():
    try:
        wasapi_idx = pa.get_host_api_info_by_type(pyaudio.paWASAPI)['index']
    except Exception:
        print("ERROR: WASAPI not available."); sys.exit(1)

    mics, loopbacks = [], []
    for i in range(pa.get_device_count()):
        d = pa.get_device_info_by_index(i)
        if d['hostApi'] != wasapi_idx or d['maxInputChannels'] == 0:
            continue
        if '[Loopback]' in d['name'] or 'loopback' in d['name'].lower():
            loopbacks.append(d)
        else:
            mics.append(d)
    return mics, loopbacks


def pick(label, devs, default_first=True):
    print(f"\n{label}:")
    if not devs:
        print("  (none found)"); return None
    for n, d in enumerate(devs):
        print(f"  [{n}] (id={d['index']}) {d['name']}  in={d['maxInputChannels']}")
    hint = "first" if default_first else "skip"
    raw = input(f"  Pick [0–{len(devs)-1}] or Enter={hint}: ").strip()
    if raw == "" and default_first:
        print(f"  → {devs[0]['name']}"); return devs[0]
    if raw == "":
        return None
    try:
        return devs[int(raw)]
    except (ValueError, IndexError):
        print("  Invalid."); return None


# ── VAD capture + transcribe pipeline ─────────────────────────────────────

def vad_capture(dev: dict, label: str, gain: float,
                client, stop: threading.Event):
    """
    Reads 30ms frames, detects speech via RMS, accumulates speech frames,
    and fires a transcription request to Groq whenever a pause is detected.
    Prints transcript live to terminal as each utterance completes.
    """
    device_id = dev['index']
    channels  = min(int(dev['maxInputChannels']), 2)
    native_sr = int(dev.get('defaultSampleRate', 48000))
    rates     = [native_sr] + [r for r in [48000, 44100, 16000] if r != native_sr]

    stream = None
    capture_rate = None
    for rate in rates:
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=int(rate * FRAME_MS / 1000),
            )
            capture_rate = rate
            print(f"  [{label}] \"{dev['name']}\" @ {rate} Hz ({channels}ch)")
            break
        except Exception as e:
            print(f"  [{label}] {rate} Hz failed: {e}")

    if stream is None:
        print(f"  [{label}] Could not open device — skipping"); return

    speech_buf    = b''       # accumulated speech PCM (16kHz mono)
    silent_frames = 0
    in_speech     = False
    transcribe_q: queue.Queue = queue.Queue()

    # Background thread drains transcription queue so capture isn't blocked
    def transcribe_worker():
        while True:
            item = transcribe_q.get()
            if item is None:
                break
            lbl, pcm, t_start = item
            wav  = to_wav(pcm)
            text = transcribe(wav, client)
            ms   = round((time.perf_counter() - t_start) * 1000)
            if text:
                dur_ms = round(len(pcm) / 2 / SAMPLE_RATE * 1000)
                print(f'\n[{lbl}] ({dur_ms}ms audio, {ms}ms API) "{text}"')
            sys.stdout.flush()

    worker = threading.Thread(target=transcribe_worker, daemon=True)
    worker.start()

    frame_samples = int(capture_rate * FRAME_MS / 1000)
    raw_buf = b''

    try:
        while not stop.is_set():
            try:
                raw_buf += stream.read(frame_samples, exception_on_overflow=False)
            except Exception:
                break

            frame_size_raw = frame_samples * channels * 2
            while len(raw_buf) >= frame_size_raw:
                raw = raw_buf[:frame_size_raw]
                raw_buf = raw_buf[frame_size_raw:]

                # normalise → mono 16kHz
                mono = stereo_to_mono(raw) if channels == 2 else raw
                pcm  = resample_to_16k(mono, capture_rate)
                if gain != 1.0:
                    pcm = boost(pcm, gain)

                r = frame_rms(pcm)

                if r >= SPEECH_RMS:
                    speech_buf    += pcm
                    silent_frames  = 0
                    in_speech      = True
                    # live indicator
                    bar = "▪" * min(int(r * 200), 20)
                    print(f"\r[{label}] {bar:<20} rms={r:.4f}", end='', flush=True)
                elif in_speech:
                    speech_buf    += pcm   # include trailing silence for natural speech
                    silent_frames += 1
                    if silent_frames >= SILENCE_FRAMES:
                        # Pause detected — flush utterance
                        min_bytes = SAMPLE_RATE * MIN_SPEECH_MS // 1000 * 2
                        if len(speech_buf) >= min_bytes:
                            transcribe_q.put((label, speech_buf, time.perf_counter()))
                        speech_buf    = b''
                        silent_frames = 0
                        in_speech     = False
                        print(f"\r[{label}] {'─'*20}              ", end='', flush=True)
    finally:
        stream.stop_stream()
        stream.close()
        # flush remaining
        if speech_buf and len(speech_buf) >= SAMPLE_RATE * MIN_SPEECH_MS // 1000 * 2:
            transcribe_q.put((label, speech_buf, time.perf_counter()))
        transcribe_q.put(None)
        worker.join(timeout=10)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
    except ImportError:
        print("groq not installed."); sys.exit(1)

    print("=" * 60)
    print(f"  DevCore Live Audio Test  (pyaudiowpatch={HAS_WPATCH})")
    print("=" * 60)

    mics, loopbacks = get_devices()
    mic_dev  = pick("Microphone (input)", mics, default_first=True)
    loop_dev = pick("System audio loopback", loopbacks, default_first=False) if loopbacks else None

    if mic_dev is None and loop_dev is None:
        print("No devices selected."); return

    print("\n" + "=" * 60)
    print("  Speak naturally — transcription fires on each pause.")
    print(f"  Speech threshold rms >= {SPEECH_RMS}  |  Mic gain x{MIC_GAIN}")
    print("  Ctrl+C to stop.")
    print("=" * 60 + "\n")

    stop = threading.Event()
    threads = []

    if mic_dev:
        t = threading.Thread(
            target=vad_capture,
            args=(mic_dev, "MIC", MIC_GAIN, client, stop),
            daemon=True,
        )
        t.start(); threads.append(t)

    if loop_dev:
        t = threading.Thread(
            target=vad_capture,
            args=(loop_dev, "SYSTEM", 1.0, client, stop),
            daemon=True,
        )
        t.start(); threads.append(t)

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        stop.set()
        for t in threads: t.join(timeout=5)
        pa.terminate()
        print("Done.")


if __name__ == "__main__":
    main()
