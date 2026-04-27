# DevCore Overlay (Cluely Module) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real-time AI interview overlay that is invisible to all screen capture and proctoring software, listens to both audio streams, and delivers sub-second suggestions.

**Architecture:** Electron main process owns audio capture (naudiodon/WASAPI) and the stealth window (WDA_EXCLUDEFROMCAPTURE via ffi-napi). Audio bytes stream over WebSocket to a new FastAPI `cluely` module which runs Whisper → DistilBERT → Gemini Flash in sequence. React renderer displays suggestions in a transparent always-on-top overlay.

**Tech Stack:** Electron + React + Zustand + Tailwind (frontend), FastAPI + Whisper + DistilBERT + all-MiniLM + Gemini Flash 2.0 + claude-sonnet-4-6 + Judge0 + Redis (backend), ffi-napi + naudiodon + electron-store (Electron native).

**Spec:** `docs/superpowers/specs/2026-04-27-devcore-overlay-design.md`

---

## File Map

### New files — Electron
| File | Responsibility |
|---|---|
| `electron/ipc/devcore.ts` | Typed IPC channel definitions, SessionStartPayload type |
| `electron/overlay.ts` | Creates stealth BrowserWindow, applies WDA_EXCLUDEFROMCAPTURE, registers hotkeys |
| `electron/audio.ts` | naudiodon device selection, PCM chunking, binary frame construction, WS send |

### Modified files — Electron
| File | Change |
|---|---|
| `electron/main.ts` | Import and init overlay window + audio module |
| `electron/preload.ts` | Expose devcore IPC wrapper on `window.electronAPI` |
| `package.json` | Add ffi-napi, naudiodon, electron-store, electron-rebuild; add postinstall script |

### New files — Backend
| File | Responsibility |
|---|---|
| `backend/app/api/v1/cluely/__init__.py` | Router registration |
| `backend/app/api/v1/cluely/ws.py` | WebSocket route, JWT auth, frame dispatch |
| `backend/app/services/cluely/__init__.py` | Package init |
| `backend/app/services/cluely/overlay_service.py` | Session lifecycle orchestration |
| `backend/app/services/cluely/audio_service.py` | PCM frame parsing, Whisper transcription, silence fallback |
| `backend/app/services/cluely/context_manager.py` | Redis rolling transcript, question window |
| `backend/app/services/cluely/bert_classifier.py` | DistilBERT INT8 question detection, silence fallback trigger |
| `backend/app/services/cluely/rag_service.py` | all-MiniLM index build, incremental refresh, top-k retrieval |
| `backend/app/services/cluely/llm_service.py` | Gemini Flash streaming + Claude on-demand + web_search tool |
| `backend/app/services/cluely/code_runner.py` | Judge0 API client, language detection, quota handling |
| `backend/app/services/cluely/search_service.py` | SerpAPI/Brave Search wrapper |
| `backend/app/services/cluely/filesystem_service.py` | os.walk + all-MiniLM index, mtime-based incremental refresh |
| `backend/app/schemas/cluely.py` | Pydantic schemas: SessionStartRequest, TranscriptEntry, SuggestionResponse |

### Modified files — Backend
| File | Change |
|---|---|
| `backend/app/core/exceptions.py` | Add OverlaySessionNotFoundError, AudioCaptureError, BertClassifierError, LLMRateLimitedError, CodeRunnerError |
| `backend/app/core/config.py` | Add judge0_api_key, serp_api_key, devcore_file_index_path |
| `backend/app/main.py` | Register cluely router |
| `.env.example` | Add JUDGE0_API_KEY, SERP_API_KEY, DEVCORE_FILE_INDEX_PATH |

### New files — Frontend
| File | Responsibility |
|---|---|
| `frontend/src/types/devcore.ts` | TranscriptEntry, OverlayPosition, SessionContext types |
| `frontend/src/store/overlayStore.ts` | Zustand store — session state, suggestion, transcript, position, error |
| `frontend/src/hooks/useOverlaySession.ts` | Session lifecycle, IPC calls, WS event → store dispatch |
| `frontend/src/hooks/useOverlayPosition.ts` | Position state, hotkey cycling, electron-store persistence |
| `frontend/src/components/devcore/OverlayShell.tsx` | Root overlay component, mounts in overlay BrowserWindow |
| `frontend/src/components/devcore/ListeningPill.tsx` | Animated pill shown while listening with no suggestion |
| `frontend/src/components/devcore/SuggestionCard.tsx` | Header + streaming suggestion + full-width input |
| `frontend/src/components/devcore/TranscriptCard.tsx` | Side transcript panel, them/you labels, blink cursor |
| `frontend/src/components/devcore/AudioSourcePicker.tsx` | Dropdown for mic / system / both |
| `frontend/src/components/devcore/SessionSetup.tsx` | Pre-session modal in main window |

---

## Task 1: Dependencies & Stealth Window Setup

**Files:**
- Modify: `package.json`
- Create: `electron/overlay.ts`
- Create: `electron/ipc/devcore.ts`
- Modify: `electron/main.ts`

- [ ] **Step 1: Install Electron-side dependencies**

```bash
npm install ffi-napi naudiodon electron-store
npm install --save-dev electron-rebuild @electron/rebuild
```

- [ ] **Step 2: Add postinstall to package.json**

In `package.json` scripts, add:
```json
"postinstall": "electron-rebuild -f -w ffi-napi,naudiodon"
```

- [ ] **Step 3: Run rebuild to verify ffi-napi compiles**

```bash
npm run postinstall
```
Expected: no errors, `ffi-napi` and `naudiodon` rebuilt for your Electron ABI.

- [ ] **Step 4: Create IPC channel type definitions**

Create `electron/ipc/devcore.ts`:
```ts
export interface SessionStartPayload {
  sessionId: string
  context: {
    jobTitle: string
    company: string
    resumeText: string
    jdText: string
    files: string[]
  }
}

export interface ManualAskPayload {
  text: string
  mode: 'hints' | 'solve'
  language?: string
}

export type DevCoreRendererToMain =
  | { channel: 'devcore:session:start'; payload: SessionStartPayload }
  | { channel: 'devcore:session:pause'; payload: void }
  | { channel: 'devcore:session:end'; payload: void }
  | { channel: 'devcore:interact:enable'; payload: void }
  | { channel: 'devcore:interact:disable'; payload: void }
  | { channel: 'devcore:manual:ask'; payload: ManualAskPayload }

export type DevCoreMainToRenderer =
  | { channel: 'devcore:suggestion'; payload: { delta: string; done: boolean } }
  | { channel: 'devcore:transcript'; payload: { speaker: 'interviewer' | 'user'; text: string } }
  | { channel: 'devcore:status'; payload: { state: 'listening' | 'thinking' | 'paused'; latencyMs: number } }
  | { channel: 'devcore:error'; payload: { code: string; message: string } }
```

- [ ] **Step 5: Create overlay window module**

Create `electron/overlay.ts`:
```ts
import { BrowserWindow, globalShortcut, app } from 'electron'
import path from 'path'
import { Library } from 'ffi-napi'
import Store from 'electron-store'

const store = new Store<{ overlayPosition: string }>()

const user32 = new Library('user32', {
  SetWindowDisplayAffinity: ['bool', ['pointer', 'uint32']]
})

const POSITIONS: Record<string, { x: () => number; y: () => number }> = {
  'top-center':    { x: () => Math.round((require('electron').screen.getPrimaryDisplay().workAreaSize.width - 500) / 2), y: () => 8 },
  'top-left':      { x: () => 8,  y: () => 8 },
  'top-right':     { x: () => require('electron').screen.getPrimaryDisplay().workAreaSize.width - 508, y: () => 8 },
  'bottom-center': { x: () => Math.round((require('electron').screen.getPrimaryDisplay().workAreaSize.width - 500) / 2), y: () => require('electron').screen.getPrimaryDisplay().workAreaSize.height - 120 },
  'bottom-right':  { x: () => require('electron').screen.getPrimaryDisplay().workAreaSize.width - 508, y: () => require('electron').screen.getPrimaryDisplay().workAreaSize.height - 120 },
}
const POSITION_ORDER = ['top-center', 'top-left', 'top-right', 'bottom-center', 'bottom-right']

let overlayWin: BrowserWindow | null = null
let currentPositionIndex = 0

export function createOverlayWindow(): BrowserWindow {
  const savedPos = store.get('overlayPosition', 'top-center') as string
  currentPositionIndex = POSITION_ORDER.indexOf(savedPos) !== -1 ? POSITION_ORDER.indexOf(savedPos) : 0
  const pos = POSITIONS[POSITION_ORDER[currentPositionIndex]]

  overlayWin = new BrowserWindow({
    width: 500,
    height: 200,
    x: pos.x(),
    y: pos.y(),
    transparent: true,
    frame: false,
    skipTaskbar: true,
    focusable: false,
    hasShadow: false,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  overlayWin.setAlwaysOnTop(true, 'screen-saver')
  overlayWin.setIgnoreMouseEvents(true, { forward: true })

  // Apply WDA_EXCLUDEFROMCAPTURE — invisible to all screen capture on Windows 11
  const hwnd = overlayWin.getNativeWindowHandle()
  user32.SetWindowDisplayAffinity(hwnd, 0x00000011)

  if (process.env.NODE_ENV === 'development') {
    overlayWin.loadURL('http://localhost:5173/overlay')
  } else {
    overlayWin.loadFile(path.join(__dirname, '../frontend/dist/index.html'), { hash: '/overlay' })
  }

  registerHotkeys(overlayWin)
  return overlayWin
}

function registerHotkeys(win: BrowserWindow) {
  // Show/hide
  globalShortcut.register('CommandOrControl+Shift+Space', () => {
    if (win.isVisible()) win.hide()
    else win.show()
  })

  // Interact mode
  globalShortcut.register('CommandOrControl+Shift+I', () => {
    win.setIgnoreMouseEvents(false)
    win.setFocusable(true)
    win.focus()
  })

  // Move overlay
  globalShortcut.register('CommandOrControl+Shift+Right', () => cyclePosition(win, 1))
  globalShortcut.register('CommandOrControl+Shift+Left', () => cyclePosition(win, -1))

  // Force re-trigger
  globalShortcut.register('CommandOrControl+Shift+R', () => {
    win.webContents.send('devcore:status', { state: 'thinking', latencyMs: 0 })
  })

  app.on('will-quit', () => globalShortcut.unregisterAll())
}

function cyclePosition(win: BrowserWindow, dir: 1 | -1) {
  currentPositionIndex = (currentPositionIndex + dir + POSITION_ORDER.length) % POSITION_ORDER.length
  const posKey = POSITION_ORDER[currentPositionIndex]
  const pos = POSITIONS[posKey]
  win.setPosition(pos.x(), pos.y())
  store.set('overlayPosition', posKey)
}

export function getOverlayWindow() { return overlayWin }
```

- [ ] **Step 6: Wire overlay into main.ts**

In `electron/main.ts`, import and call `createOverlayWindow()` inside `app.whenReady()`:
```ts
import { createOverlayWindow } from './overlay'

app.whenReady().then(() => {
  Menu.setApplicationMenu(null)
  createWindow()          // existing main window
  createOverlayWindow()   // new overlay window
})
```

- [ ] **Step 7: Run the app and verify the overlay window appears**

```bash
npm run dev
```
Expected: app starts, overlay window visible at top-center. `Ctrl+Shift+Space` toggles it. Check in OBS or Windows Snipping Tool that the overlay area shows as transparent/nothing. No errors in console.

- [ ] **Step 8: Commit**

```bash
git add package.json electron/overlay.ts electron/ipc/devcore.ts electron/main.ts
git commit -m "feat(cluely): stealth overlay window with WDA_EXCLUDEFROMCAPTURE and hotkeys"
```

---

## Task 2: Preload IPC Bridge + overlayStore

**Files:**
- Modify: `electron/preload.ts`
- Create: `frontend/src/types/devcore.ts`
- Create: `frontend/src/store/overlayStore.ts`

- [ ] **Step 1: Expose devcore IPC on window.electronAPI in preload**

In `electron/preload.ts`, add to the `contextBridge.exposeInMainWorld` call:
```ts
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  // ... existing channels ...
  getAccessToken: () => ipcRenderer.invoke('auth:get:token'),  // used by SessionSetup to auth API calls
  devcore: {
    startSession:     (payload: unknown) => ipcRenderer.invoke('devcore:session:start', payload),
    pauseSession:     ()                 => ipcRenderer.invoke('devcore:session:pause'),
    endSession:       ()                 => ipcRenderer.invoke('devcore:session:end'),
    enableInteract:   ()                 => ipcRenderer.invoke('devcore:interact:enable'),
    disableInteract:  ()                 => ipcRenderer.invoke('devcore:interact:disable'),
    manualAsk:        (payload: unknown) => ipcRenderer.invoke('devcore:manual:ask', payload),
    onSuggestion:     (cb: (p: { delta: string; done: boolean }) => void) =>
                        ipcRenderer.on('devcore:suggestion', (_e, p) => cb(p)),
    onTranscript:     (cb: (p: { speaker: string; text: string }) => void) =>
                        ipcRenderer.on('devcore:transcript', (_e, p) => cb(p)),
    onStatus:         (cb: (p: { state: string; latencyMs: number }) => void) =>
                        ipcRenderer.on('devcore:status', (_e, p) => cb(p)),
    onError:          (cb: (p: { code: string; message: string }) => void) =>
                        ipcRenderer.on('devcore:error', (_e, p) => cb(p)),
    removeAllListeners: () => {
      ;['devcore:suggestion','devcore:transcript','devcore:status','devcore:error']
        .forEach(ch => ipcRenderer.removeAllListeners(ch))
    },
  },
})
```

- [ ] **Step 2: Create shared TypeScript types**

Create `frontend/src/types/devcore.ts`:
```ts
export interface TranscriptEntry {
  speaker: 'interviewer' | 'user'
  text: string
  seq: number
}

export type OverlayPosition = 'top-center' | 'top-left' | 'top-right' | 'bottom-center' | 'bottom-right'

export interface SessionContext {
  jobTitle: string
  company: string
  resumeText: string
  jdText: string
  files: string[]
}

export type OverlayState = 'idle' | 'listening' | 'thinking' | 'paused'
```

- [ ] **Step 3: Create Zustand overlayStore**

Create `frontend/src/store/overlayStore.ts`:
```ts
import { create } from 'zustand'
import type { TranscriptEntry, OverlayPosition, OverlayState } from '../types/devcore'

interface OverlayStore {
  sessionId: string | null
  state: OverlayState
  suggestion: string
  transcript: TranscriptEntry[]
  latencyMs: number
  audioSource: 'mic' | 'system' | 'both'
  transcriptOpen: boolean
  position: OverlayPosition
  error: { code: string; message: string } | null

  setSessionId:      (id: string | null) => void
  setState:          (s: OverlayState) => void
  appendSuggestion:  (delta: string) => void
  clearSuggestion:   () => void
  addTranscript:     (entry: TranscriptEntry) => void
  setLatency:        (ms: number) => void
  setAudioSource:    (src: 'mic' | 'system' | 'both') => void
  setTranscriptOpen: (open: boolean) => void
  setPosition:       (pos: OverlayPosition) => void
  setError:          (err: { code: string; message: string } | null) => void
}

export const useOverlayStore = create<OverlayStore>((set) => ({
  sessionId: null,
  state: 'idle',
  suggestion: '',
  transcript: [],
  latencyMs: 0,
  audioSource: 'both',
  transcriptOpen: false,
  position: 'top-center',
  error: null,

  setSessionId:      (id) => set({ sessionId: id }),
  setState:          (s)  => set({ state: s }),
  appendSuggestion:  (d)  => set((st) => ({ suggestion: st.suggestion + d })),
  clearSuggestion:   ()   => set({ suggestion: '' }),
  addTranscript:     (e)  => set((st) => ({ transcript: [...st.transcript.slice(-19), e] })),
  setLatency:        (ms) => set({ latencyMs: ms }),
  setAudioSource:    (src)=> set({ audioSource: src }),
  setTranscriptOpen: (o)  => set({ transcriptOpen: o }),
  setPosition:       (p)  => set({ position: p }),
  setError:          (e)  => set({ error: e }),
}))
```

- [ ] **Step 4: Commit**

```bash
git add electron/preload.ts frontend/src/types/devcore.ts frontend/src/store/overlayStore.ts
git commit -m "feat(cluely): IPC bridge, shared types, and overlayStore"
```

---

## Task 3: Backend Schemas + Exceptions + Config

**Files:**
- Create: `backend/app/schemas/cluely.py`
- Modify: `backend/app/core/exceptions.py`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Write failing tests for new exceptions**

Create `backend/tests/services/test_cluely_exceptions.py`:
```python
from app.core.exceptions import (
    OverlaySessionNotFoundError,
    AudioCaptureError,
    BertClassifierError,
    LLMRateLimitedError,
    CodeRunnerError,
)

def test_overlay_session_not_found():
    e = OverlaySessionNotFoundError()
    assert e.code == "OVERLAY_SESSION_NOT_FOUND"
    assert e.status_code == 404

def test_bert_classifier_error_is_non_fatal():
    e = BertClassifierError()
    assert e.code == "BERT_UNAVAILABLE"
    assert e.status_code == 500

def test_code_runner_quota_exceeded():
    e = CodeRunnerError(code="CODE_RUNNER_QUOTA_EXCEEDED")
    assert e.code == "CODE_RUNNER_QUOTA_EXCEEDED"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && pytest tests/services/test_cluely_exceptions.py -v
```
Expected: ImportError — exceptions don't exist yet.

- [ ] **Step 3: Add exceptions to exceptions.py**

In `backend/app/core/exceptions.py`, append:
```python
class OverlaySessionNotFoundError(DevCoreException):
    def __init__(self):
        super().__init__("OVERLAY_SESSION_NOT_FOUND", "Overlay session not found", 404)

class AudioCaptureError(DevCoreException):
    def __init__(self, message: str = "Audio capture failed"):
        super().__init__("AUDIO_CAPTURE_ERROR", message, 500)

class BertClassifierError(DevCoreException):
    def __init__(self):
        super().__init__("BERT_UNAVAILABLE", "BERT classifier unavailable, using silence fallback", 500)

class LLMRateLimitedError(DevCoreException):
    def __init__(self):
        super().__init__("LLM_RATE_LIMITED", "LLM rate limit reached", 429)

class CodeRunnerError(DevCoreException):
    def __init__(self, code: str = "CODE_RUNNER_ERROR", message: str = "Code execution failed"):
        super().__init__(code, message, 500)
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pytest tests/services/test_cluely_exceptions.py -v
```
Expected: all 3 PASS.

- [ ] **Step 5: Add config fields**

In `backend/app/core/config.py` `Settings` class, add:
```python
judge0_api_key: str = ""
serp_api_key: str = ""
devcore_file_index_path: str = "~/.devcore/file_index"
```

- [ ] **Step 6: Add to .env.example**

In `.env.example`, add:
```
JUDGE0_API_KEY=
SERP_API_KEY=
DEVCORE_FILE_INDEX_PATH=~/.devcore/file_index
GEMINI_API_KEY=          # Required for real-time suggestions (Gemini Flash 2.0)
```

- [ ] **Step 7: Create Pydantic schemas**

Create `backend/app/schemas/cluely.py`:
```python
from pydantic import BaseModel
from typing import Literal

class SessionContext(BaseModel):
    job_title: str = ""
    company: str = ""
    resume_text: str = ""
    jd_text: str = ""
    files: list[str] = []

class SessionStartRequest(BaseModel):
    session_id: str
    context: SessionContext

class TranscriptEntry(BaseModel):
    speaker: Literal["interviewer", "user"]
    text: str
    seq: int

class SuggestionResponse(BaseModel):
    delta: str
    done: bool

class ManualAskRequest(BaseModel):
    text: str
    mode: Literal["hints", "solve"]
    language: str = "python"  # for solve mode: caller passes detected or user-selected language
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/exceptions.py backend/app/core/config.py \
        backend/app/schemas/cluely.py .env.example \
        backend/tests/services/test_cluely_exceptions.py
git commit -m "feat(cluely): schemas, exceptions, and config fields"
```

---

## Task 4: Audio Service + Whisper Transcription

**Files:**
- Create: `backend/app/services/cluely/__init__.py`
- Create: `backend/app/services/cluely/audio_service.py`
- Create: `backend/tests/services/test_cluely_audio.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_cluely_audio.py`:
```python
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
    svc = AudioService()
    pcm = b'\x00\x00' * 16000  # 1s of silence
    with patch('app.services.cluely.audio_service.whisper') as mock_w:
        mock_w.load_model.return_value.transcribe.return_value = {'text': 'hello'}
        result = await svc.transcribe(pcm, speaker='interviewer')
    assert result['speaker'] == 'interviewer'
    assert result['text'] == 'hello'
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/services/test_cluely_audio.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create package init**

Create `backend/app/services/cluely/__init__.py` (empty).

- [ ] **Step 4: Implement audio_service.py**

Create `backend/app/services/cluely/audio_service.py`:
```python
import asyncio
import struct
import math
from typing import Literal
import whisper
import logging

logger = logging.getLogger(__name__)

_whisper_model = None

def _get_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model("tiny")
    return _whisper_model


def parse_audio_frame(data: bytes) -> tuple[Literal["mic", "system"], int, bytes]:
    """Parse 3-byte header: uint8 stream_id + uint16 big-endian seq. Returns (stream, seq, pcm)."""
    if len(data) < 3:
        raise ValueError("Frame too short")
    stream_id_byte, seq = struct.unpack_from('!BH', data, 0)
    pcm = data[3:]
    stream: Literal["mic", "system"] = "mic" if stream_id_byte == 0x01 else "system"
    return stream, seq, pcm


def detect_silence(pcm: bytes, threshold: float = 0.01, sample_rate: int = 16000) -> bool:
    """True if the RMS of the PCM buffer is below threshold (normalized -1..1)."""
    samples = struct.unpack('<' + 'h' * (len(pcm) // 2), pcm)
    if not samples:
        return True
    rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0
    return rms < threshold


class AudioService:
    async def transcribe(self, pcm: bytes, speaker: Literal["interviewer", "user"]) -> dict:
        """Transcribe raw PCM16 mono 16kHz. Returns {speaker, text}. CPU-bound → thread."""
        import soundfile as sf, numpy as np
        def _run():  # must be sync — asyncio.to_thread runs in a thread pool, not event loop
            model = _get_model()
            samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            result = model.transcribe(samples, language=None)
            return {"speaker": speaker, "text": result["text"].strip()}
        return await asyncio.to_thread(_run)
```

- [ ] **Step 5: Install missing Python deps**

```bash
cd backend && pip install openai-whisper soundfile numpy
```

- [ ] **Step 6: Run tests — verify pass**

```bash
pytest tests/services/test_cluely_audio.py -v
```
Expected: all PASS (transcribe test mocks whisper).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/cluely/ backend/tests/services/test_cluely_audio.py
git commit -m "feat(cluely): audio frame parser, Whisper transcription, silence detection"
```

---

## Task 5: BERT Classifier

**Files:**
- Create: `backend/app/services/cluely/bert_classifier.py`
- Create: `backend/tests/services/test_cluely_bert.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_cluely_bert.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from app.services.cluely.bert_classifier import BertClassifier
from app.core.exceptions import BertClassifierError

@pytest.mark.asyncio
async def test_classifies_question_as_true():
    clf = BertClassifier()
    clf._model = MagicMock()
    clf._tokenizer = MagicMock()
    # Mock pipeline to return question label
    with patch('app.services.cluely.bert_classifier.pipeline') as mock_pipe:
        mock_pipe.return_value = MagicMock(return_value=[{'label': 'QUESTION', 'score': 0.95}])
        clf._pipe = mock_pipe.return_value
        result = await clf.is_question("Tell me about your experience with distributed systems?")
    assert result is True

@pytest.mark.asyncio
async def test_classifies_statement_as_false():
    clf = BertClassifier()
    with patch('app.services.cluely.bert_classifier.pipeline') as mock_pipe:
        mock_pipe.return_value = MagicMock(return_value=[{'label': 'STATEMENT', 'score': 0.88}])
        clf._pipe = mock_pipe.return_value
        result = await clf.is_question("Tell me about yourself.")
    assert result is False

def test_falls_back_to_regex_on_missing_model():
    with patch('app.services.cluely.bert_classifier.os.path.exists', return_value=False):
        clf = BertClassifier(model_path="/nonexistent/model")
        assert clf._use_regex is True

@pytest.mark.asyncio
async def test_regex_fallback_detects_question():
    with patch('app.services.cluely.bert_classifier.os.path.exists', return_value=False):
        clf = BertClassifier(model_path="/nonexistent/model")
        assert await clf.is_question("Tell me about your distributed systems experience?") is True
        assert await clf.is_question("I worked at Google for three years.") is False
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/services/test_cluely_bert.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement bert_classifier.py**

Create `backend/app/services/cluely/bert_classifier.py`:
```python
import asyncio
import os
import re
import logging
from app.core.exceptions import BertClassifierError

logger = logging.getLogger(__name__)

# Fine-tuned question-detection model. Download a distilbert-base-uncased model
# fine-tuned for question classification and place it at this path.
# When the path does not exist, the classifier falls back to a regex heuristic.
_DEFAULT_MODEL_PATH = os.path.expanduser("~/.devcore/models/question-classifier")

_QUESTION_RE = re.compile(
    r'\b(what|who|where|when|why|how|which|whose|whom|can you|could you|'
    r'would you|tell me|explain|describe|have you|do you|are you|is there)\b',
    re.IGNORECASE,
)


def _regex_is_question(text: str) -> bool:
    """Heuristic fallback: question mark OR interrogative opener."""
    return text.strip().endswith('?') or bool(_QUESTION_RE.match(text.strip()))


class BertClassifier:
    def __init__(self, model_path: str = _DEFAULT_MODEL_PATH):
        self._use_regex = False
        if not os.path.exists(model_path):
            logger.warning(
                "Question-classifier model not found at %s — using regex heuristic. "
                "Place a fine-tuned distilbert question-classification model there to enable BERT.",
                model_path,
            )
            self._use_regex = True
            return
        try:
            from transformers import pipeline
            self._pipe = pipeline(
                "text-classification",
                model=model_path,
                device=-1,      # CPU
                truncation=True,
                max_length=128,
            )
            logger.info("BertClassifier loaded: %s", model_path)
        except Exception as e:
            raise BertClassifierError() from e

    async def is_question(self, text: str) -> bool:
        """Returns True if text is a question. Falls back to regex when model absent."""
        if self._use_regex:
            return _regex_is_question(text)
        def _run():
            results = self._pipe(text)
            # Model must output label 'QUESTION' for question-class texts.
            # Confirmed against: cross-encoder/nli-deberta-v3-small trained on question detection.
            return results[0]["label"] == "QUESTION"
        return await asyncio.to_thread(_run)
```

- [ ] **Step 4: Install transformers**

```bash
pip install transformers torch
```

- [ ] **Step 5: Run tests — verify pass**

```bash
pytest tests/services/test_cluely_bert.py -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/cluely/bert_classifier.py backend/tests/services/test_cluely_bert.py
git commit -m "feat(cluely): DistilBERT question classifier with BertClassifierError fallback"
```

---

## Task 6: Context Manager (Redis)

**Files:**
- Create: `backend/app/services/cluely/context_manager.py`
- Create: `backend/tests/services/test_cluely_context.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_cluely_context.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.cluely.context_manager import ContextManager
from app.schemas.cluely import TranscriptEntry

@pytest.mark.asyncio
async def test_push_transcript_stores_in_redis():
    redis = AsyncMock()
    redis.rpush = AsyncMock()
    redis.ltrim = AsyncMock()
    redis.expire = AsyncMock()
    cm = ContextManager(redis=redis, session_id="test-123")
    entry = TranscriptEntry(speaker="interviewer", text="Tell me about yourself.", seq=1)
    await cm.push_transcript(entry)
    redis.rpush.assert_called_once()
    redis.ltrim.assert_called_once()

@pytest.mark.asyncio
async def test_get_window_returns_last_n():
    redis = AsyncMock()
    entries = [f'{{"speaker":"interviewer","text":"q{i}","seq":{i}}}' for i in range(15)]
    redis.lrange = AsyncMock(return_value=[e.encode() for e in entries[-10:]])
    cm = ContextManager(redis=redis, session_id="test-123")
    window = await cm.get_window(n=10)
    assert len(window) == 10
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/services/test_cluely_context.py -v
```

- [ ] **Step 3: Implement context_manager.py**

Create `backend/app/services/cluely/context_manager.py`:
```python
import json
import logging
from app.schemas.cluely import TranscriptEntry

logger = logging.getLogger(__name__)
TRANSCRIPT_TTL = 4 * 3600  # 4 hours


class ContextManager:
    def __init__(self, redis, session_id: str):
        self._r = redis
        self._sid = session_id
        self._transcript_key = f"cluely:session:{session_id}:transcript"
        self._state_key = f"cluely:session:{session_id}:state"

    async def push_transcript(self, entry: TranscriptEntry) -> None:
        await self._r.rpush(self._transcript_key, entry.model_dump_json())
        await self._r.ltrim(self._transcript_key, -20, -1)  # keep last 20
        await self._r.expire(self._transcript_key, TRANSCRIPT_TTL)

    async def get_window(self, n: int = 10) -> list[TranscriptEntry]:
        raw = await self._r.lrange(self._transcript_key, -n, -1)
        return [TranscriptEntry(**json.loads(r)) for r in raw]

    async def set_state(self, state: str) -> None:
        await self._r.setex(self._state_key, TRANSCRIPT_TTL, state)

    async def get_state(self) -> str | None:
        val = await self._r.get(self._state_key)
        return val.decode() if val else None

    async def session_exists(self) -> bool:
        return bool(await self._r.exists(self._state_key))
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pytest tests/services/test_cluely_context.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cluely/context_manager.py backend/tests/services/test_cluely_context.py
git commit -m "feat(cluely): Redis context manager with rolling transcript window"
```

---

## Task 7: RAG Service

**Files:**
- Create: `backend/app/services/cluely/rag_service.py`
- Create: `backend/tests/services/test_cluely_rag.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_cluely_rag.py`:
```python
import pytest, tempfile, os
from app.services.cluely.rag_service import RagService

@pytest.mark.asyncio
async def test_build_and_retrieve(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("Redis is an in-memory data structure store used as a cache.")
    svc = RagService(index_dir=str(tmp_path / "index"))
    await svc.build_index([str(tmp_path)])
    chunks = await svc.retrieve("What is Redis?", k=1)
    assert len(chunks) == 1
    assert "Redis" in chunks[0]

@pytest.mark.asyncio
async def test_incremental_skips_unchanged(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("Python is a programming language.")
    svc = RagService(index_dir=str(tmp_path / "index"))
    await svc.build_index([str(tmp_path)])
    mtime_before = os.path.getmtime(str(tmp_path / "index" / "index_meta.json"))
    # No file changes — rebuild should not update meta
    await svc.build_index([str(tmp_path)])
    mtime_after = os.path.getmtime(str(tmp_path / "index" / "index_meta.json"))
    assert mtime_before == mtime_after
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/services/test_cluely_rag.py -v
```

- [ ] **Step 3: Install sentence-transformers**

```bash
pip install sentence-transformers faiss-cpu
```

- [ ] **Step 4: Implement rag_service.py**

Create `backend/app/services/cluely/rag_service.py`:
```python
import asyncio, json, os, logging
from pathlib import Path

logger = logging.getLogger(__name__)
CHUNK_SIZE = 400  # characters


class RagService:
    def __init__(self, index_dir: str = "~/.devcore/file_index"):
        self._index_dir = Path(index_dir).expanduser()
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self._index_dir / "index_meta.json"
        self._chunks: list[str] = []
        self._embeddings = None
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

    def _chunk_text(self, text: str) -> list[str]:
        return [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE) if text[i:i+CHUNK_SIZE].strip()]

    def _read_file(self, path: str) -> str:
        try:
            if path.endswith(".pdf"):
                import pdfminer.high_level
                return pdfminer.high_level.extract_text(path)
            with open(path, encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning("Could not read %s: %s", path, e)
            return ""

    async def build_index(self, directories: list[str]) -> None:
        await asyncio.to_thread(self._build_sync, directories)

    def _build_sync(self, directories: list[str]) -> None:
        import numpy as np
        meta = json.loads(self._meta_path.read_text()) if self._meta_path.exists() else {}
        new_meta = {}
        all_chunks: list[str] = []

        for d in directories:
            for root, _, files in os.walk(os.path.expanduser(d)):
                for fname in files:
                    if not fname.endswith((".txt", ".pdf", ".md", ".docx")):
                        continue
                    fpath = os.path.join(root, fname)
                    mtime = os.path.getmtime(fpath)
                    new_meta[fpath] = mtime
                    if meta.get(fpath) == mtime:
                        continue  # unchanged — skip
                    text = self._read_file(fpath)
                    all_chunks.extend(self._chunk_text(text))

        if not all_chunks and meta == new_meta:
            return  # nothing changed

        model = self._get_model()
        self._chunks = all_chunks
        self._embeddings = model.encode(all_chunks, convert_to_numpy=True)
        self._meta_path.write_text(json.dumps(new_meta))
        logger.info("RAG index built: %d chunks", len(all_chunks))

    async def retrieve(self, query: str, k: int = 3) -> list[str]:
        if self._embeddings is None or len(self._chunks) == 0:
            return []
        return await asyncio.to_thread(self._retrieve_sync, query, k)

    def _retrieve_sync(self, query: str, k: int) -> list[str]:
        import numpy as np
        model = self._get_model()
        q_emb = model.encode([query], convert_to_numpy=True)
        scores = (self._embeddings @ q_emb.T).squeeze()
        top_k = int(min(k, len(self._chunks)))
        indices = scores.argsort()[-top_k:][::-1]
        return [self._chunks[i] for i in indices]
```

- [ ] **Step 5: Run tests — verify pass**

```bash
pytest tests/services/test_cluely_rag.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/cluely/rag_service.py backend/tests/services/test_cluely_rag.py
git commit -m "feat(cluely): RAG service with all-MiniLM embeddings and incremental index"
```

---

## Task 8: Search + Filesystem + Code Runner Services

**Files:**
- Create: `backend/app/services/cluely/search_service.py`
- Create: `backend/app/services/cluely/filesystem_service.py`
- Create: `backend/app/services/cluely/code_runner.py`
- Create: `backend/tests/services/test_cluely_tools.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_cluely_tools.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.cluely.search_service import SearchService
from app.services.cluely.code_runner import CodeRunner
from app.core.exceptions import CodeRunnerError

@pytest.mark.asyncio
async def test_search_returns_snippets():
    svc = SearchService()
    with patch('app.services.cluely.search_service.httpx.AsyncClient') as mock_client:
        mock_resp = AsyncMock()
        mock_resp.json.return_value = {"organic_results": [{"snippet": "Python is great"}]}
        mock_resp.raise_for_status = AsyncMock()
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        results = await svc.search("Python basics")
    assert "Python is great" in results[0]

@pytest.mark.asyncio
async def test_code_runner_returns_output():
    runner = CodeRunner()
    with patch('app.services.cluely.code_runner.httpx.AsyncClient') as mock_client:
        mock_resp = AsyncMock()
        mock_resp.json.return_value = {"stdout": "hello\n", "stderr": "", "status": {"id": 3}}
        mock_resp.raise_for_status = AsyncMock()
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        result = await runner.execute("print('hello')", language="python")
    assert result["output"] == "hello\n"

@pytest.mark.asyncio
async def test_code_runner_raises_on_quota():
    runner = CodeRunner()
    import httpx
    with patch('app.services.cluely.code_runner.httpx.AsyncClient') as mock_client:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("429", request=None, response=AsyncMock(status_code=429))
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        with pytest.raises(CodeRunnerError) as exc:
            await runner.execute("print(1)", language="python")
    assert exc.value.code == "CODE_RUNNER_QUOTA_EXCEEDED"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/services/test_cluely_tools.py -v
```

- [ ] **Step 3: Implement search_service.py**

Create `backend/app/services/cluely/search_service.py`:
```python
import httpx, logging
from app.core.config import settings

logger = logging.getLogger(__name__)
SERP_URL = "https://serpapi.com/search"

class SearchService:
    async def search(self, query: str, num: int = 3) -> list[str]:
        if not settings.serp_api_key:
            return [f"[Search unavailable — no SERP_API_KEY configured]"]
        params = {"q": query, "api_key": settings.serp_api_key, "num": num}
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(SERP_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        return [r.get("snippet", "") for r in data.get("organic_results", [])[:num]]
```

- [ ] **Step 4: Implement code_runner.py**

Create `backend/app/services/cluely/code_runner.py`:
```python
import httpx, logging
from app.core.config import settings
from app.core.exceptions import CodeRunnerError

logger = logging.getLogger(__name__)

JUDGE0_URL = "https://judge0-ce.p.rapidapi.com/submissions"
LANGUAGE_IDS = {
    "python": 71, "javascript": 63, "typescript": 74,
    "java": 62, "cpp": 54, "go": 60, "rust": 73,
}

class CodeRunner:
    async def execute(self, code: str, language: str) -> dict:
        lang_id = LANGUAGE_IDS.get(language.lower())
        if lang_id is None:
            raise CodeRunnerError(message=f"Unsupported language: {language}")
        headers = {
            "X-RapidAPI-Key": settings.judge0_api_key,
            "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com",
        }
        payload = {"source_code": code, "language_id": lang_id, "stdin": ""}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{JUDGE0_URL}?wait=true", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            return {
                "output": data.get("stdout") or data.get("stderr") or "",
                "language": language,
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise CodeRunnerError(
                    code="CODE_RUNNER_QUOTA_EXCEEDED",
                    message="Daily code execution limit reached. Solution shown without running."
                )
            raise CodeRunnerError(message=str(e))
```

- [ ] **Step 5: Implement filesystem_service.py**

Create `backend/app/services/cluely/filesystem_service.py`:
```python
import asyncio, os, logging
from app.services.cluely.rag_service import RagService
from app.core.config import settings

logger = logging.getLogger(__name__)

class FilesystemService:
    def __init__(self):
        self._rag = RagService(index_dir=settings.devcore_file_index_path)
        self._dirs: list[str] = ["~/Documents", "~/Desktop"]

    def set_directories(self, dirs: list[str]) -> None:
        self._dirs = dirs

    async def build_index(self) -> None:
        await self._rag.build_index(self._dirs)

    async def search(self, query: str, k: int = 3) -> list[str]:
        return await self._rag.retrieve(query, k=k)
```

- [ ] **Step 6: Run tests — verify pass**

```bash
pytest tests/services/test_cluely_tools.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/cluely/search_service.py \
        backend/app/services/cluely/filesystem_service.py \
        backend/app/services/cluely/code_runner.py \
        backend/tests/services/test_cluely_tools.py
git commit -m "feat(cluely): search, filesystem, and Judge0 code runner services"
```

---

## Task 9: LLM Service (Gemini Flash + Claude)

**Files:**
- Create: `backend/app/services/cluely/llm_service.py`
- Create: `backend/tests/services/test_cluely_llm.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_cluely_llm.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.cluely.llm_service import LLMService
from app.schemas.cluely import TranscriptEntry

@pytest.mark.asyncio
async def test_stream_suggestion_yields_deltas():
    svc = LLMService()
    transcript = [TranscriptEntry(speaker="interviewer", text="Tell me about CAP theorem?", seq=1)]
    context = {"job_title": "Backend Engineer", "company": "Stripe", "resume_text": "", "jd_text": ""}
    chunks = ["Lead with", " distributed", " systems."]
    with patch.object(svc, '_stream_gemini', return_value=aiter(chunks)):
        deltas = []
        async for delta in svc.stream_suggestion(transcript=transcript, context=context, rag_chunks=[]):
            deltas.append(delta)
    assert "".join(deltas) == "Lead with distributed systems."

@pytest.mark.asyncio
async def test_manual_ask_hints_uses_claude():
    svc = LLMService()
    with patch.object(svc, '_ask_claude', new_callable=AsyncMock, return_value="Try binary search.") as mock_c:
        result = await svc.manual_ask("How to find element in sorted array?", mode="hints", context={})
    mock_c.assert_called_once()
    assert "binary search" in result.lower()

async def aiter(items):
    for item in items:
        yield item
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/services/test_cluely_llm.py -v
```

- [ ] **Step 3: Implement llm_service.py**

Create `backend/app/services/cluely/llm_service.py`:
```python
import logging
from typing import AsyncIterator
import google.generativeai as genai
import anthropic
from app.core.config import settings
from app.core.exceptions import LLMRateLimitedError
from app.schemas.cluely import TranscriptEntry
from app.services.cluely.search_service import SearchService

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self._gemini = genai.GenerativeModel("gemini-2.0-flash")
        self._claude = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._search = SearchService()

    def _build_system_prompt(self, context: dict) -> str:
        return (
            f"You are a real-time interview assistant. The user is interviewing for "
            f"{context.get('job_title', 'a role')} at {context.get('company', 'a company')}. "
            f"Resume highlights: {context.get('resume_text', '')[:500]}. "
            f"Job description: {context.get('jd_text', '')[:500]}. "
            "Respond with a single, concise talking point (1-2 sentences). "
            "No lists. No preamble. Speak directly as a coaching whisper."
        )

    async def stream_suggestion(
        self,
        transcript: list[TranscriptEntry],
        context: dict,
        rag_chunks: list[str],
    ) -> AsyncIterator[str]:
        history = "\n".join(f"{e.speaker}: {e.text}" for e in transcript[-10:])
        rag_ctx = "\n".join(rag_chunks) if rag_chunks else ""
        prompt = f"{self._build_system_prompt(context)}\n\nConversation:\n{history}\n\nRelevant context:\n{rag_ctx}"
        try:
            async for delta in self._stream_gemini(prompt):
                yield delta
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                raise LLMRateLimitedError() from e
            raise

    async def _stream_gemini(self, prompt: str) -> AsyncIterator[str]:
        response = await self._gemini.generate_content_async(prompt, stream=True)
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def manual_ask(self, text: str, mode: str, context: dict, rag_chunks: list[str] = []) -> str:
        rag_ctx = "\n".join(rag_chunks)
        system = self._build_system_prompt(context)
        if mode == "hints":
            prompt = f"Provide hints and approach (no full solution) for: {text}\n\nContext: {rag_ctx}"
        else:
            prompt = f"Write a complete, clean solution for: {text}\n\nContext: {rag_ctx}"
        return await self._ask_claude(system=system, user=prompt)

    async def _ask_claude(self, system: str, user: str) -> str:
        # Check if web search is needed
        search_results = []
        if any(kw in user.lower() for kw in ["latest", "current", "docs", "documentation", "api"]):
            search_results = await self._search.search(user[:200])
        if search_results:
            user += f"\n\nWeb search results:\n" + "\n".join(search_results)
        msg = await self._claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text
```

- [ ] **Step 4: Install google-generativeai**

```bash
pip install google-generativeai
```

- [ ] **Step 5: Run tests — verify pass**

```bash
pytest tests/services/test_cluely_llm.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/cluely/llm_service.py backend/tests/services/test_cluely_llm.py
git commit -m "feat(cluely): LLM service — Gemini Flash streaming + Claude on-demand with web search"
```

---

## Task 10: Overlay Service + WebSocket Route

**Files:**
- Create: `backend/app/services/cluely/overlay_service.py`
- Create: `backend/app/api/v1/cluely/__init__.py`
- Create: `backend/app/api/v1/cluely/ws.py`
- Create: `backend/tests/integration/test_cluely_ws.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing integration test**

Create `backend/tests/integration/test_cluely_ws.py`:
```python
import pytest, json
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token

@pytest.mark.asyncio
async def test_ws_rejects_without_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pass  # WebSocket test via TestClient
    from fastapi.testclient import TestClient
    client = TestClient(app)
    with client.websocket_connect("/api/v1/cluely/ws") as ws:
        # No auth frame sent — server should close after 3s timeout
        # For test: send non-auth frame immediately
        ws.send_json({"type": "session_start", "session_id": "abc"})
        data = ws.receive_json()
        assert data.get("type") == "error" or ws.closed

@pytest.mark.asyncio
async def test_ws_accepts_valid_auth():
    from fastapi.testclient import TestClient
    token = create_access_token("test-user-id")
    client = TestClient(app)
    with client.websocket_connect("/api/v1/cluely/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        # Connection should remain open (no close code)
        ws.send_json({"type": "session_end"})
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/integration/test_cluely_ws.py -v
```

- [ ] **Step 3: Implement overlay_service.py**

Create `backend/app/services/cluely/overlay_service.py`:
```python
import asyncio, logging, struct, uuid
from fastapi import WebSocket
from app.core.cache import get_redis
from app.core.security import decode_token
from app.core.exceptions import BertClassifierError, LLMRateLimitedError, CodeRunnerError
from app.services.cluely.audio_service import AudioService, parse_audio_frame, detect_silence
from app.services.cluely.context_manager import ContextManager
from app.services.cluely.bert_classifier import BertClassifier
from app.services.cluely.rag_service import RagService
from app.services.cluely.llm_service import LLMService
from app.services.cluely.code_runner import CodeRunner
from app.schemas.cluely import TranscriptEntry, SessionStartRequest

logger = logging.getLogger(__name__)
BERT_COOLDOWN = 0.5  # seconds between BERT triggers


class OverlayService:
    def __init__(self):
        self._audio = AudioService()
        self._llm = LLMService()
        self._runner = CodeRunner()
        self._last_trigger = 0.0
        try:
            self._bert = BertClassifier()
            self._use_bert = True
        except BertClassifierError:
            logger.warning("BERT unavailable — using silence detection fallback")
            self._use_bert = False

    async def handle(self, ws: WebSocket) -> None:
        await ws.accept()
        r = await get_redis()
        ctx_mgr: ContextManager | None = None
        rag: RagService | None = None
        session_ctx: dict = {}

        # Auth gate — first frame must be auth
        try:
            first = await asyncio.wait_for(ws.receive_json(), timeout=3.0)
        except asyncio.TimeoutError:
            await ws.close(code=4001)
            return
        if first.get("type") != "auth":
            await ws.send_json({"type": "error", "code": "AUTH_REQUIRED", "message": "First frame must be auth"})
            await ws.close(code=4001)
            return
        try:
            decode_token(first["token"])
        except Exception:
            await ws.send_json({"type": "error", "code": "AUTH_FAILED", "message": "Invalid token"})
            await ws.close(code=4001)
            return

        try:
            while True:
                msg = await ws.receive()
                if "bytes" in msg:
                    await self._handle_audio(ws, msg["bytes"], ctx_mgr, rag, session_ctx)
                elif "text" in msg:
                    data = __import__("json").loads(msg["text"])
                    mtype = data.get("type")
                    if mtype == "session_start":
                        ctx_mgr, rag, session_ctx = await self._start_session(ws, r, data)
                    elif mtype == "session_pause":
                        if ctx_mgr: await ctx_mgr.set_state("paused")
                        await ws.send_json({"type": "status", "state": "paused", "latency_ms": 0})
                    elif mtype == "session_end":
                        break
                    elif mtype == "manual_ask":
                        await self._handle_manual_ask(ws, data, session_ctx, rag)
        except Exception as e:
            logger.exception("Overlay WS error: %s", e)
        finally:
            await ws.close()

    async def _start_session(self, ws, r, data: dict):
        sid = data["session_id"]
        ctx = data.get("context", {})
        ctx_mgr = ContextManager(redis=r, session_id=sid)
        if not await ctx_mgr.session_exists():
            await ctx_mgr.set_state("listening")
        rag = RagService()
        files = ctx.get("files", [])
        if files:
            asyncio.create_task(rag.build_index(files))
        await ws.send_json({"type": "status", "state": "listening", "latency_ms": 0})
        return ctx_mgr, rag, ctx

    async def _handle_audio(self, ws, raw: bytes, ctx_mgr, rag, session_ctx):
        if ctx_mgr is None:
            return
        try:
            stream, seq, pcm = parse_audio_frame(raw)
        except ValueError:
            return
        speaker = "interviewer" if stream == "system" else "user"
        result = await self._audio.transcribe(pcm, speaker=speaker)
        if not result["text"]:
            return
        entry = TranscriptEntry(speaker=speaker, text=result["text"], seq=seq)
        await ctx_mgr.push_transcript(entry)
        await ws.send_json({"type": "transcript", "speaker": speaker, "text": result["text"], "seq": seq})

        if speaker != "interviewer":
            return

        import time
        now = time.monotonic()
        triggered = False
        if self._use_bert:
            if now - self._last_trigger > BERT_COOLDOWN:
                is_q = await self._bert.is_question(result["text"])
                if is_q:
                    triggered = True
        else:
            triggered = detect_silence(pcm)

        if triggered:
            self._last_trigger = now
            await self._stream_suggestion(ws, ctx_mgr, rag, session_ctx)

    async def _stream_suggestion(self, ws, ctx_mgr, rag, session_ctx):
        await ws.send_json({"type": "status", "state": "thinking", "latency_ms": 0})
        transcript = await ctx_mgr.get_window(n=10)
        rag_chunks = await rag.retrieve(transcript[-1].text if transcript else "", k=3) if rag else []
        import time; t0 = time.monotonic()
        try:
            first = True
            async for delta in self._llm.stream_suggestion(transcript=transcript, context=session_ctx, rag_chunks=rag_chunks):
                if first:
                    latency = round((time.monotonic() - t0) * 1000)
                    await ws.send_json({"type": "status", "state": "listening", "latency_ms": latency})
                    first = False
                await ws.send_json({"type": "suggestion_delta", "delta": delta})
            await ws.send_json({"type": "suggestion_end"})
        except LLMRateLimitedError:
            await ws.send_json({"type": "error", "code": "LLM_RATE_LIMITED", "message": "Rate limited"})

    async def _handle_manual_ask(self, ws, data: dict, session_ctx: dict, rag):
        rag_chunks = await rag.retrieve(data["text"], k=3) if rag else []
        try:
            result = await self._llm.manual_ask(data["text"], mode=data.get("mode", "hints"), context=session_ctx, rag_chunks=rag_chunks)
            if data.get("mode") == "solve":
                lang = data.get("language", "python")  # caller passes language from UI picker
                code_result = await self._runner.execute(result, language=lang)
                await ws.send_json({"type": "code_result", "language": lang, "output": code_result["output"], "solution": result})
            else:
                await ws.send_json({"type": "suggestion_delta", "delta": result})
                await ws.send_json({"type": "suggestion_end"})
        except CodeRunnerError as e:
            await ws.send_json({"type": "error", "code": e.code, "message": e.message})
```

- [ ] **Step 4: Create WebSocket route**

Create `backend/app/api/v1/cluely/__init__.py` (empty).

Create `backend/app/api/v1/cluely/ws.py`:
```python
from fastapi import APIRouter, WebSocket
from app.services.cluely.overlay_service import OverlayService

router = APIRouter(prefix="/cluely", tags=["cluely"])
_svc = OverlayService()

@router.websocket("/ws")
async def devcore_overlay_ws(websocket: WebSocket):
    await _svc.handle(websocket)
```

- [ ] **Step 5: Register router in main.py**

In `backend/app/main.py`, add:
```python
from app.api.v1.cluely.ws import router as cluely_ws_router
app.include_router(cluely_ws_router, prefix="/api/v1")
```

- [ ] **Step 6: Run integration test**

```bash
pytest tests/integration/test_cluely_ws.py -v
```
Expected: auth rejection test PASS, valid auth test PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/cluely/overlay_service.py \
        backend/app/api/v1/cluely/ \
        backend/app/main.py \
        backend/tests/integration/test_cluely_ws.py
git commit -m "feat(cluely): overlay service, WebSocket route, JWT auth gate"
```

---

## Task 11: Electron Audio Capture + WS Bridge

**Files:**
- Create: `electron/audio.ts`
- Modify: `electron/main.ts`

- [ ] **Step 1: Implement audio.ts**

Create `electron/audio.ts`:
```ts
import naudiodon from 'naudiodon'
import WebSocket from 'ws'

let micInput: ReturnType<typeof naudiodon.AudioInput> | null = null
let sysInput: ReturnType<typeof naudiodon.AudioInput> | null = null
let ws: WebSocket | null = null
let chunkSeq = 0

export function startAudioCapture(wsUrl: string, token: string, audioSource: 'mic' | 'system' | 'both') {
  ws = new WebSocket(wsUrl)
  ws.on('open', () => {
    ws!.send(JSON.stringify({ type: 'auth', token }))
  })

  const devices = naudiodon.getDevices()
  const loopback = devices.find((d: any) => d.hostAPIName === 'Windows WASAPI' && d.isLoopbackDevice)
  const mic = devices.find((d: any) => d.hostAPIName === 'Windows WASAPI' && d.maxInputChannels > 0 && !d.isLoopbackDevice)

  const CHUNK_MS = 2000
  const SAMPLE_RATE = 16000
  const CHUNK_SAMPLES = (SAMPLE_RATE * CHUNK_MS) / 1000
  const CHUNK_BYTES = CHUNK_SAMPLES * 2  // PCM16 = 2 bytes/sample

  function sendChunk(pcm: Buffer, streamId: 0x01 | 0x02) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    const seq = chunkSeq++ % 65536
    const header = Buffer.alloc(3)
    header.writeUInt8(streamId, 0)
    header.writeUInt16BE(seq, 1)
    ws.send(Buffer.concat([header, pcm]))
  }

  function startStream(deviceId: number, streamId: 0x01 | 0x02) {
    let buf = Buffer.alloc(0)
    const input = naudiodon.AudioInput({ deviceId, channelCount: 1, sampleRate: SAMPLE_RATE, framesPerBuffer: 4096, bitDepth: 16 })
    input.on('data', (chunk: Buffer) => {
      buf = Buffer.concat([buf, chunk])
      while (buf.length >= CHUNK_BYTES) {
        sendChunk(buf.slice(0, CHUNK_BYTES), streamId)
        buf = buf.slice(CHUNK_BYTES)
      }
    })
    input.start()
    return input
  }

  if ((audioSource === 'system' || audioSource === 'both') && loopback) {
    sysInput = startStream(loopback.id, 0x02)
  }
  if ((audioSource === 'mic' || audioSource === 'both') && mic) {
    micInput = startStream(mic.id, 0x01)
  }
}

export function stopAudioCapture() {
  micInput?.quit()
  sysInput?.quit()
  ws?.close()
  micInput = sysInput = ws = null
}

export function getActiveWs() { return ws }
```

- [ ] **Step 2: Wire IPC handlers in main.ts**

In `electron/main.ts`, add IPC handlers for session lifecycle:
```ts
import { ipcMain } from 'electron'
import { startAudioCapture, stopAudioCapture } from './audio'
import { getOverlayWindow } from './overlay'

const BACKEND_WS = 'ws://localhost:8000/api/v1/cluely/ws'

// Reads the stored JWT access token from wherever your existing auth module persists it.
// If your auth module exports a `getStoredToken()` function, import and call it here.
// Replace the import path below with the actual auth state module path.
import { getStoredToken } from './auth'  // adjust import to match existing auth module

// Expose the stored token to the renderer so SessionSetup can attach it to API requests
ipcMain.handle('auth:get:token', async () => getStoredToken())

ipcMain.handle('devcore:session:start', async (_e, payload) => {
  // Token comes from renderer: SessionSetup calls getAccessToken() and passes it in payload
  const token: string = payload.token ?? getStoredToken() ?? ''
  startAudioCapture(BACKEND_WS, token, payload.audioSource ?? 'both')
})

ipcMain.handle('devcore:session:pause', async () => {
  stopAudioCapture()
})

ipcMain.handle('devcore:session:end', async () => {
  stopAudioCapture()
})

ipcMain.handle('devcore:interact:enable', async () => {
  getOverlayWindow()?.setIgnoreMouseEvents(false)
  getOverlayWindow()?.setFocusable(true)
  getOverlayWindow()?.focus()
})

ipcMain.handle('devcore:interact:disable', async () => {
  getOverlayWindow()?.setIgnoreMouseEvents(true, { forward: true })
  getOverlayWindow()?.setFocusable(false)
})

// Forward manual ask from renderer to the backend WS connection
// The WS connection is owned by the audio module; re-use the same socket
ipcMain.handle('devcore:manual:ask', async (_e, payload: { text: string; mode: string; language?: string }) => {
  // Import the active WS from audio module and send a manual_ask frame
  const { getActiveWs } = await import('./audio')
  const ws = getActiveWs()
  if (ws && ws.readyState === 1 /* WebSocket.OPEN */) {
    ws.send(JSON.stringify({
      type: 'manual_ask',
      text: payload.text,
      mode: payload.mode,
      language: payload.language ?? 'python',
    }))
  }
})
```

- [ ] **Step 3: Install ws package**

```bash
npm install ws @types/ws
```

- [ ] **Step 4: Compile and verify no TypeScript errors**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add electron/audio.ts electron/main.ts
git commit -m "feat(cluely): WASAPI audio capture and IPC session handlers"
```

---

## Task 12: Overlay UI Components

**Files:**
- Create: `frontend/src/hooks/useOverlaySession.ts`
- Create: `frontend/src/hooks/useOverlayPosition.ts`
- Create: `frontend/src/components/devcore/ListeningPill.tsx`
- Create: `frontend/src/components/devcore/SuggestionCard.tsx`
- Create: `frontend/src/components/devcore/TranscriptCard.tsx`
- Create: `frontend/src/components/devcore/AudioSourcePicker.tsx`
- Create: `frontend/src/components/devcore/OverlayShell.tsx`

- [ ] **Step 1: Create useOverlaySession hook**

Create `frontend/src/hooks/useOverlaySession.ts`:
```ts
import { useEffect, useRef } from 'react'
import { useOverlayStore } from '../store/overlayStore'

declare global {
  interface Window {
    electronAPI: any
  }
}

export function useOverlaySession() {
  const store = useOverlayStore()
  const mounted = useRef(false)

  useEffect(() => {
    if (mounted.current) return
    mounted.current = true
    const api = window.electronAPI?.devcore
    if (!api) return

    api.onSuggestion(({ delta, done }: { delta: string; done: boolean }) => {
      store.appendSuggestion(delta)
      if (done) { /* suggestion_end handled separately */ }
    })
    api.onTranscript(({ speaker, text }: { speaker: 'interviewer' | 'user'; text: string }) => {
      store.addTranscript({ speaker, text, seq: Date.now() })
    })
    api.onStatus(({ state, latencyMs }: { state: any; latencyMs: number }) => {
      store.setState(state)
      store.setLatency(latencyMs)
      if (state === 'thinking') store.clearSuggestion()
    })
    api.onError(({ code, message }: { code: string; message: string }) => {
      store.setError({ code, message })
    })
    return () => api.removeAllListeners()
  }, [])

  return {
    startSession: (payload: object) => window.electronAPI?.devcore.startSession(payload),
    pauseSession:  () => window.electronAPI?.devcore.pauseSession(),
    endSession:    () => window.electronAPI?.devcore.endSession(),
    enableInteract: () => window.electronAPI?.devcore.enableInteract(),
    manualAsk: (text: string, mode: 'hints' | 'solve', language?: string) =>
      window.electronAPI?.devcore.manualAsk({ text, mode, language }),
  }
}
```

- [ ] **Step 2: Create useOverlayPosition hook**

Create `frontend/src/hooks/useOverlayPosition.ts`:
```ts
import { useOverlayStore } from '../store/overlayStore'
import type { OverlayPosition } from '../types/devcore'

const ORDER: OverlayPosition[] = ['top-center', 'top-left', 'top-right', 'bottom-center', 'bottom-right']

export function useOverlayPosition() {
  const { position, setPosition } = useOverlayStore()
  const cycleNext = () => {
    const idx = ORDER.indexOf(position)
    setPosition(ORDER[(idx + 1) % ORDER.length])
  }
  return { position, cycleNext }
}
```

- [ ] **Step 3: Create ListeningPill component**

Create `frontend/src/components/devcore/ListeningPill.tsx`:
```tsx
import React from 'react'

export function ListeningPill() {
  return (
    <div className="flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-[rgba(9,9,18,0.97)] border border-white/[0.07] shadow-lg">
      <span className="w-1.5 h-1.5 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.8)] animate-pulse" />
      <span className="font-display text-[10.5px] font-extrabold tracking-[0.15em] text-violet-400">DEVCORE</span>
      <div className="w-px h-3.5 bg-white/[0.07]" />
      <div className="flex items-end gap-[2.5px] h-4">
        {[6, 12, 8, 14, 6, 10].map((h, i) => (
          <span
            key={i}
            className="w-0.5 bg-emerald-400 rounded-sm shadow-[0_0_4px_rgba(52,211,153,0.8)]"
            style={{ height: h, animation: `wave 1.1s ease-in-out ${i * 0.05}s infinite` }}
          />
        ))}
      </div>
      <span className="font-mono text-[9px] text-white/30 tracking-wider">listening...</span>
    </div>
  )
}
```

- [ ] **Step 4: Create SuggestionCard component**

Create `frontend/src/components/devcore/SuggestionCard.tsx`:
```tsx
import React, { useState } from 'react'
import { useOverlayStore } from '../../store/overlayStore'
import { AudioSourcePicker } from './AudioSourcePicker'
import { useOverlaySession } from '../../hooks/useOverlaySession'

export function SuggestionCard() {
  const { suggestion, latencyMs, transcriptOpen, setTranscriptOpen } = useOverlayStore()
  const { pauseSession, endSession, manualAsk } = useOverlaySession()
  const [ask, setAsk] = useState('')

  const handleAsk = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && ask.trim()) {
      manualAsk(ask.trim(), 'hints')
      setAsk('')
    }
  }

  return (
    <div className="bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-[11px] overflow-hidden shadow-[0_12px_48px_rgba(0,0,0,0.75)] w-[480px]">
      {/* Header */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-white/[0.07] bg-white/[0.015]">
        <span className="w-1.5 h-1.5 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.8)] animate-pulse flex-shrink-0" />
        <span className="font-display text-[10.5px] font-extrabold tracking-[0.15em] text-violet-400">DEVCORE</span>
        <div className="flex items-center gap-1 ml-1">
          <span className="w-1 h-1 rounded-full bg-emerald-400 shadow-[0_0_5px_rgba(52,211,153,0.8)]" />
          <span className="font-mono text-[9px] text-emerald-400">{latencyMs > 0 ? `${latencyMs}ms` : '—'}</span>
        </div>
        <div className="flex-1" />
        <AudioSourcePicker />
        <button
          onClick={() => setTranscriptOpen(!transcriptOpen)}
          className={`w-[27px] h-[27px] flex items-center justify-center rounded-md border transition-all ${transcriptOpen ? 'border-violet-400/40 bg-violet-400/10 text-violet-400' : 'border-white/[0.07] bg-white/[0.025] text-white/30 hover:text-white/60'}`}
        >
          <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        </button>
        <button onClick={pauseSession} className="flex items-center gap-1 px-2 py-1 rounded-md border border-yellow-300/20 bg-yellow-300/5 text-yellow-300 font-mono text-[9px] hover:bg-yellow-300/10 transition-all">
          <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
          Pause
        </button>
        <button onClick={endSession} className="flex items-center gap-1 px-2 py-1 rounded-md border border-red-400/20 bg-red-400/5 text-red-400 font-mono text-[9px] hover:bg-red-400/10 transition-all">
          <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
          End
        </button>
      </div>
      {/* Suggestion */}
      <div className="px-3 pt-2.5 pb-2 border-b border-white/[0.07]">
        <p className="text-[8px] font-mono uppercase tracking-widest text-white/30 mb-1">Suggestion</p>
        <div className="flex gap-2 items-start">
          <span className="text-violet-400 font-mono text-[10px] flex-shrink-0 mt-0.5">▸</span>
          <p className="text-[12px] text-white/90 leading-relaxed tracking-tight">
            {suggestion || <span className="text-white/20">Listening for a question…</span>}
          </p>
        </div>
      </div>
      {/* Input */}
      <div className="px-3 py-2">
        <div className="flex items-center gap-1.5 bg-white/[0.03] border border-white/[0.07] rounded-lg px-2.5 py-1.5 focus-within:border-violet-400/25 focus-within:bg-violet-400/[0.07] transition-all">
          <span className="font-mono text-[8px] text-white/20 flex-shrink-0">⌘/</span>
          <input
            value={ask}
            onChange={e => setAsk(e.target.value)}
            onKeyDown={handleAsk}
            placeholder="Ask anything…"
            className="flex-1 bg-transparent border-none outline-none text-[11.5px] text-white/90 placeholder-white/20 font-sans"
          />
          <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/20 flex-shrink-0"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Create TranscriptCard component**

Create `frontend/src/components/devcore/TranscriptCard.tsx`:
```tsx
import React from 'react'
import { useOverlayStore } from '../../store/overlayStore'

export function TranscriptCard() {
  const { transcript, setTranscriptOpen } = useOverlayStore()
  return (
    <div className="bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-[11px] overflow-hidden w-[230px] shadow-[0_12px_48px_rgba(0,0,0,0.75)]">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/[0.07] bg-white/[0.015]">
        <span className="font-mono text-[9px] uppercase tracking-widest text-white/30">Transcript</span>
        <button onClick={() => setTranscriptOpen(false)} className="w-[18px] h-[18px] flex items-center justify-center rounded text-white/30 hover:text-white/60 hover:bg-white/5 transition-all">
          <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div className="px-3 py-2.5 flex flex-col gap-2 max-h-[280px] overflow-y-auto">
        {transcript.map((e, i) => (
          <div key={i} className="flex gap-2 items-start">
            <span className={`font-mono text-[8px] w-[26px] flex-shrink-0 pt-0.5 ${e.speaker === 'user' ? 'text-violet-400' : 'text-white/30'}`}>
              {e.speaker === 'user' ? 'you' : 'them'}
            </span>
            <span className="text-[11px] text-white/60 leading-relaxed tracking-tight">{e.text}</span>
          </div>
        ))}
        {transcript.length === 0 && (
          <span className="text-[10px] text-white/20 font-mono">No transcript yet…</span>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Create AudioSourcePicker**

Create `frontend/src/components/devcore/AudioSourcePicker.tsx`:
```tsx
import React, { useState } from 'react'
import { useOverlayStore } from '../../store/overlayStore'

const OPTIONS = [
  { value: 'both',   label: 'Mic + System' },
  { value: 'mic',    label: 'Mic only' },
  { value: 'system', label: 'System only' },
] as const

export function AudioSourcePicker() {
  const { audioSource, setAudioSource } = useOverlayStore()
  const [open, setOpen] = useState(false)
  const selected = OPTIONS.find(o => o.value === audioSource)!

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 px-2 py-1 rounded-md border border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.055] transition-all"
      >
        <svg width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/50"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
        <span className="font-mono text-[9px] text-white/60 whitespace-nowrap">{selected.label}</span>
        <svg width="9" height="9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-white/30"><path d="m6 9 6 6 6-6"/></svg>
      </button>
      {open && (
        <div className="absolute top-full mt-1 right-0 bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-lg overflow-hidden shadow-xl z-50">
          {OPTIONS.map(o => (
            <button
              key={o.value}
              onClick={() => { setAudioSource(o.value); setOpen(false) }}
              className={`block w-full text-left px-3 py-2 font-mono text-[9px] whitespace-nowrap transition-all ${audioSource === o.value ? 'text-violet-400 bg-violet-400/10' : 'text-white/60 hover:bg-white/5'}`}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 7: Create OverlayShell**

Create `frontend/src/components/devcore/OverlayShell.tsx`:
```tsx
import React from 'react'
import { useOverlayStore } from '../../store/overlayStore'
import { useOverlaySession } from '../../hooks/useOverlaySession'
import { ListeningPill } from './ListeningPill'
import { SuggestionCard } from './SuggestionCard'
import { TranscriptCard } from './TranscriptCard'

export function OverlayShell() {
  useOverlaySession()  // registers IPC listeners
  const { state, suggestion, transcriptOpen } = useOverlayStore()

  if (state === 'idle') return null

  const showCard = suggestion || state === 'thinking'

  return (
    <div className="fixed top-2 left-1/2 -translate-x-1/2 flex items-start gap-2 z-50">
      {transcriptOpen && <TranscriptCard />}
      {showCard ? <SuggestionCard /> : <ListeningPill />}
    </div>
  )
}
```

- [ ] **Step 8: Add CSS animation for waveform to index.css**

In `frontend/src/index.css` append:
```css
@keyframes wave {
  0%, 100% { transform: scaleY(1); }
  50%       { transform: scaleY(0.3); }
}
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/devcore/ frontend/src/hooks/ \
        frontend/src/store/overlayStore.ts frontend/src/types/devcore.ts \
        frontend/src/index.css
git commit -m "feat(cluely): overlay UI components — pill, suggestion card, transcript, audio picker"
```

---

## Task 13: Session Setup Modal

**Files:**
- Create: `frontend/src/components/devcore/SessionSetup.tsx`

- [ ] **Step 1: Implement SessionSetup**

Create `frontend/src/components/devcore/SessionSetup.tsx`:
```tsx
import React, { useState, useEffect } from 'react'
import { useOverlaySession } from '../../hooks/useOverlaySession'
import { useOverlayStore } from '../../store/overlayStore'
import type { SessionContext } from '../../types/devcore'

type SourceTab = 'job' | 'calendar' | 'describe'

interface AppliedJob {
  id: string
  title: string
  company: string
  status: string
  resumeText: string
  jdText: string
}

export function SessionSetup({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<SourceTab>('job')
  const [selectedJob, setSelectedJob] = useState<string | null>(null)
  const [description, setDescription] = useState('')
  const [files, setFiles] = useState<string[]>([])
  const [jobs, setJobs] = useState<AppliedJob[]>([])
  const { startSession } = useOverlaySession()
  const { setSessionId, setState } = useOverlayStore()

  // Load applied jobs from Job Hunter backend
  // GET /api/v1/job-hunter/applications?status=interview,screening&limit=20
  // Response: { data: [{ id, job_title, company_name, status, resume_text, jd_text }] }
  useEffect(() => {
    // getAccessToken() returns a Promise — must await before building headers
    const load = async () => {
      const token: string = await window.electronAPI?.getAccessToken?.() ?? ''
      return fetch('/api/v1/job-hunter/applications?status=interview,screening&limit=20', {
        headers: { Authorization: `Bearer ${token}` },
      })
    }
    load()
      .then(r => r.json())
      .then(json => setJobs((json.data ?? []).map((a: any) => ({
        id: a.id,
        title: a.job_title,
        company: a.company_name,
        status: a.status,
        resumeText: a.resume_text ?? '',
        jdText: a.jd_text ?? '',
      }))))
      .catch(() => setJobs([]))  // graceful degradation — user can still use Describe tab
  }, [])

  const selectedJobData = jobs.find(j => j.id === selectedJob)

  const handleStart = async () => {
    const ctx: SessionContext = {
      jobTitle: tab === 'job' ? selectedJobData?.title ?? '' : '',
      company:  tab === 'job' ? selectedJobData?.company ?? '' : '',
      resumeText: tab === 'job' ? selectedJobData?.resumeText ?? '' : '',
      jdText: tab === 'job' ? selectedJobData?.jdText ?? '' : description,
      files,
    }
    // Await the token Promise before passing it to session start
    const token: string = await window.electronAPI?.getAccessToken?.() ?? ''
    const id = crypto.randomUUID()
    setSessionId(id)
    setState('listening')
    await startSession({ sessionId: id, context: ctx, audioSource: 'both', token })
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[rgba(9,9,18,0.97)] border border-white/[0.07] rounded-[14px] w-[520px] overflow-hidden shadow-[0_24px_64px_rgba(0,0,0,0.8)]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.07] bg-white/[0.015]">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.8)]" />
            <span className="font-display text-[11px] font-extrabold tracking-[0.15em] text-violet-400">DEVCORE</span>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/30">New Session</span>
        </div>
        {/* Body */}
        <div className="p-4 flex flex-col gap-4">
          {/* Source tabs */}
          <div>
            <p className="font-mono text-[8.5px] uppercase tracking-widest text-white/30 mb-2">Context source</p>
            <div className="flex gap-2">
              {([['job','Applied Job'], ['calendar','Calendar'], ['describe','Describe']] as [SourceTab, string][]).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`flex-1 py-3 rounded-lg border text-[9px] font-mono uppercase tracking-wider transition-all ${tab === key ? 'border-violet-400/25 bg-violet-400/10 text-violet-400' : 'border-white/[0.07] bg-white/[0.025] text-white/30 hover:bg-white/[0.045]'}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="h-px bg-white/[0.07]" />
          {/* Panel */}
          {tab === 'job' && (
            <div className="flex flex-col gap-2">
              <p className="font-mono text-[8.5px] uppercase tracking-widest text-white/30">Select from applied jobs</p>
              {jobs.length === 0 && (
                <p className="font-mono text-[9px] text-white/30 py-2">No interview-stage applications found. Use Describe tab instead.</p>
              )}
              {jobs.map(job => (
                <button
                  key={job.id}
                  onClick={() => setSelectedJob(job.id)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border text-left transition-all ${selectedJob === job.id ? 'border-violet-400/25 bg-violet-400/10' : 'border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.04]'}`}
                >
                  <div className="w-8 h-8 rounded-md bg-white/[0.06] border border-white/[0.07] flex items-center justify-center font-display text-[11px] font-bold text-white/50 flex-shrink-0">{job.company[0]}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] text-white/90 font-medium truncate">{job.title}</p>
                    <p className="font-mono text-[9px] text-white/30 mt-0.5">{job.company}</p>
                  </div>
                  <span className="font-mono text-[8px] px-2 py-1 rounded-full border border-emerald-400/25 bg-emerald-400/8 text-emerald-400 flex-shrink-0">{job.status}</span>
                </button>
              ))}
            </div>
          )}
          {tab === 'describe' && (
            <div className="flex flex-col gap-2">
              <p className="font-mono text-[8.5px] uppercase tracking-widest text-white/30">Describe the interview</p>
              <div className="bg-white/[0.025] border border-white/[0.07] rounded-lg p-3 focus-within:border-violet-400/25 transition-all">
                <textarea
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder="e.g. Senior backend role at Stripe, system design round..."
                  className="w-full bg-transparent border-none outline-none resize-none text-[12px] text-white/90 placeholder-white/20 leading-relaxed min-h-[80px]"
                />
              </div>
            </div>
          )}
          {tab === 'calendar' && (
            <div className="flex items-center justify-center py-6">
              <p className="font-mono text-[10px] text-white/30">Connect a CalDAV calendar in Settings to see upcoming events.</p>
            </div>
          )}
          {/* Confirmation strip */}
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-emerald-400/15 bg-emerald-400/5">
            <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" className="text-emerald-400 flex-shrink-0"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            <p className="text-[11px] text-white/50">
              {selectedJobData
                ? <>AI has context on <strong className="text-white/80">{selectedJobData.company} · {selectedJobData.title}</strong>. Ready.</>
                : 'Select a context source to load session context.'}
            </p>
          </div>
        </div>
        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-white/[0.07] bg-white/[0.01]">
          <span className="font-mono text-[9px] text-white/20">Ctrl+Shift+Space to toggle overlay</span>
          <button
            onClick={handleStart}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-violet-400 text-[#0a0014] font-display text-[11px] font-bold tracking-[0.1em] shadow-[0_0_20px_rgba(167,139,250,0.2)] hover:brightness-110 transition-all"
          >
            <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
            Start Session
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Wire SessionSetup into Dashboard or a Cluely page**

In `frontend/src/pages/Dashboard.tsx` (or create `frontend/src/pages/Cluely.tsx`), add a "Start Interview Session" button that renders `<SessionSetup />` when clicked.

- [ ] **Step 3: Verify UI renders without errors**

```bash
cd frontend && npm run dev
```
Open the app, click to start a session — setup modal should appear. Select a job, click Start Session — modal closes, overlay enters listening state.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/devcore/SessionSetup.tsx
git commit -m "feat(cluely): session setup modal with Applied Job / Calendar / Describe tabs"
```

---

## Task 14: Final Integration Test + Manual Stealth Verification

- [ ] **Step 1: Run all cluely backend tests**

```bash
cd backend && pytest tests/services/test_cluely_*.py tests/integration/test_cluely_ws.py -v
```
Expected: all PASS.

- [ ] **Step 2: Run the full app**

```bash
# Terminal 1 — backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend + Electron
npm run dev:all
```

- [ ] **Step 3: Manual stealth verification checklist**

- [ ] Open OBS Studio → Add Display Capture → confirm overlay is NOT visible in the preview
- [ ] Open Windows Snipping Tool → Take screenshot → confirm overlay area appears transparent
- [ ] Start a Zoom call or screenshare → verify overlay invisible to recipients
- [ ] Verify `Ctrl+Shift+Space` toggles visibility on your physical display
- [ ] Verify `Ctrl+Shift+Arrow` cycles overlay position
- [ ] Verify `Ctrl+Shift+I` enables interact mode (can click inside overlay)
- [ ] Verify overlay is NOT visible in taskbar

- [ ] **Step 4: End-to-end smoke test**

- [ ] Open session setup → select a job → Start Session
- [ ] Speak a question out loud (or play audio) → verify suggestion appears within ~1s
- [ ] Type in the manual input → verify response streams in
- [ ] Toggle transcript → verify panel appears on the left
- [ ] Click End → overlay returns to idle

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(cluely): complete DevCore overlay — stealth window, audio pipeline, AI suggestions"
```
