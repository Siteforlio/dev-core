# DevCore Overlay (Cluely Module) — Design Spec
**Date:** 2026-04-27
**Status:** Approved
**Platform:** Windows 11 (primary), cross-platform Electron
**Architecture compliance:** Follows ARCHITECTURE.md — read that first.

---

## 1. Vision

A real-time AI overlay that sits invisibly on top of every application — screen shares, browser-based exams, video calls — listening to the conversation and delivering instant, context-aware suggestions. Completely undetectable to all screen capture and proctoring software. Sub-second response time.

---

## 2. Core Principles

- **Stealth first:** Invisible to all capture APIs. The user sees it; nothing else does.
- **Sub-second response:** BERT fires the LLM before the interviewer finishes speaking. Suggestions stream token-by-token.
- **Zero friction:** Session setup pulls context automatically from Job Hunter. Files optional.
- **Cost discipline:** Local models for speed-critical tasks, Gemini Flash for real-time suggestions, Claude Sonnet for on-demand complex asks.

---

## 3. Architecture

### 3.1 High-Level

```
[Electron Main Process]
  ├── Overlay BrowserWindow  (WDA_EXCLUDEFROMCAPTURE, always-on-top, no taskbar)
  ├── WASAPI Audio Capture   (naudiodon — runs HERE, not in Python)
  ├── IPC handlers           (electron/ipc/devcore.ts)
  └── Global hotkey handler  (globalShortcut)

[Electron Renderer (React)]
  ├── Session Setup UI
  ├── Overlay UI (OverlayShell, SuggestionCard, TranscriptCard, ListeningPill)
  ├── overlayStore (Zustand)
  └── useOverlaySession hook → IPC → main process → WebSocket → backend

[FastAPI Backend — cluely module]
  ├── WebSocket /api/v1/cluely/ws
  ├── audio_service.py       — receives audio bytes, runs Whisper tiny locally
  ├── context_manager.py     — rolling transcript, Redis state (cluely:session:{id}:*)
  ├── bert_classifier.py     — DistilBERT question detection (~10ms)
  ├── rag_service.py         — all-MiniLM embeddings over session files
  ├── llm_service.py         — Gemini Flash (streaming) + claude-sonnet-4-6 (on-demand)
  └── code_runner.py         — Judge0 API (v1)

[Shared Infrastructure]
  ├── Redis   — session state with TTL (cluely:session:{id}:*)
  ├── PostgreSQL — user auth (existing), optional transcript persistence (later)
  └── SerpAPI / Brave Search — web search tool, called by LLM
```

### 3.2 Technology Choices

All choices follow ARCHITECTURE.md §2. New additions to the stack are marked *(new)*.

| Concern | Technology | Reason |
|---|---|---|
| Stealth | `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` | Win32 API, window appears transparent to all capture on Win11 |
| Always-on-top | `win.setAlwaysOnTop(true, 'screen-saver')` | Floats above fullscreen apps |
| Taskbar hiding | `skipTaskbar: true` | No icon visible anywhere |
| Frontend styling | Tailwind CSS | Per ARCHITECTURE.md §2 |
| Frontend state | Zustand (`overlayStore.ts`) | Per ARCHITECTURE.md §5.2 |
| Audio capture | `naudiodon` (Electron main process) *(new)* | WASAPI loopback + mic, Windows. Runs in Node, not Python |
| Transcription | Whisper tiny (local, Python) | Already in stack. Receives audio bytes from Electron via WebSocket |
| Question detection | DistilBERT classifier (local) *(new)* | ~10ms with quantized distilled model, CPU |
| RAG embeddings | all-MiniLM-L6-v2 (local) *(new)* | ~5ms lookup, zero API cost |
| Real-time suggestions | Gemini Flash 2.0 (streaming) *(new)* | ~$0.03/session, ~300ms first token. Used for this path only because sub-second latency is a hard requirement. Claude Sonnet remains default for all other modules per ARCHITECTURE.md §2. |
| On-demand asks + code | `claude-sonnet-4-6` | Default LLM per ARCHITECTURE.md §2 |
| Code execution | Judge0 API *(new)* | Sandboxed. v1 only — local Docker considered for v2 |
| Web search | SerpAPI or Brave Search *(new)* | LLM tool, called automatically, not a UI element |
| File system search | Python `os.walk` + all-MiniLM index *(new)* | Silent LLM tool. No UI button. Scope limited to user-selected directories. |
| Session state | Redis, TTL=4h | `cluely:session:{id}:state`, `cluely:session:{id}:transcript` per ARCHITECTURE.md §6.3 |

---

## 4. Stealth Layer

### 4.1 Screen Capture Invisibility

After the Electron `BrowserWindow` is created in the main process, `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)` is called via `ffi-napi`:

```ts
// electron/main.ts — after win.loadURL(...)
import { Library } from 'ffi-napi'

const user32 = new Library('user32', {
  SetWindowDisplayAffinity: ['bool', ['pointer', 'uint32']]
})
const hwnd = win.getNativeWindowHandle()  // returns Buffer containing raw HWND (64-bit on Win64)
user32.SetWindowDisplayAffinity(hwnd, 0x00000011)  // WDA_EXCLUDEFROMCAPTURE
// Buffer passed as 'pointer' is correct — ffi-napi reads the raw bytes as the handle value.
// ref-napi is NOT needed here and must not be imported.
```

On Windows 11, this makes the window appear fully transparent (showing whatever is behind it) in all capture APIs. On Windows 10 it shows as black — acceptable degradation.

`ffi-napi` must be rebuilt for the specific Electron ABI. Add to `package.json`:
```json
"scripts": {
  "postinstall": "electron-rebuild -f -w ffi-napi"
}
```
No separate C++ build or `node-gyp` needed beyond what `electron-rebuild` handles.

### 4.2 Window Properties

```ts
// BrowserWindow constructor
const win = new BrowserWindow({
  transparent: true,
  frame: false,
  skipTaskbar: true,
  focusable: false,
  hasShadow: false,
  webPreferences: {
    nodeIntegration: false,
    contextIsolation: true,
    preload: path.join(__dirname, 'preload.js')
  }
})

// Post-creation — level 'screen-saver' floats above fullscreen apps
win.setAlwaysOnTop(true, 'screen-saver')
win.setIgnoreMouseEvents(true, { forward: true })  // click-through by default
```

### 4.3 Hotkeys (Global, `globalShortcut`)

| Hotkey | Action |
|---|---|
| `Ctrl+Shift+Space` | Show / hide overlay |
| `Ctrl+Shift+I` | Interact mode — calls `setIgnoreMouseEvents(false)` temporarily |
| `Ctrl+Shift+Arrow` | Move overlay between top-center, corners, edges |
| `Ctrl+Shift+R` | Force re-trigger AI response |

Position is persisted to `electron-store` between sessions.

---

## 5. Session Setup

A modal that appears when the user starts a new session. Three context source tabs:

1. **Applied Job** — lists applied jobs from the Job Hunter module. The backend fetches these via an internal service call to `JobHunterService.get_applications_for_overlay(user_id)` — never by importing Job Hunter internals directly (ARCHITECTURE.md §4.1). Returns job title, company, tailored resume text, and job description text. Auto-selected if a calendar event matches.

2. **Calendar** — lists upcoming calendar events fetched via `CalendarService.get_upcoming_events()` (existing CalDAV integration). Note: Google Calendar and Outlook OAuth are **not** currently integrated — only CalDAV sources. Events must be added to a connected CalDAV calendar to appear here.

3. **Describe** — free-text description + file drop zone (PDF, DOCX, TXT). Fallback for anything outside the system.

Additional files can always be attached regardless of source. The screen shows a green strip confirming what context the AI has loaded before the user hits **Start Session**. File index build begins asynchronously when **Start Session** is pressed — a progress indicator shows in the overlay's listening pill state until indexing completes (typically 2–10s for a normal Documents folder).

---

## 6. Audio Pipeline

Audio capture runs **entirely in the Electron main process** via `naudiodon`. The Python backend never calls any audio device directly.

```
Electron main process
  // Device selection — run at session start
  const devices = naudiodon.getDevices()
  const loopback = devices.find(d => d.hostAPIName === 'Windows WASAPI' && d.isLoopbackDevice)
  const mic = devices.find(d => d.hostAPIName === 'Windows WASAPI' && d.maxInputChannels > 0 && !d.isLoopbackDevice)
  // If loopback not found, fall back to "Stereo Mix" if available, else system-only disabled
  // Both shown in AudioSourcePicker dropdown; user can select individual devices if auto-detection is wrong

  naudiodon.AudioInput({ deviceId: loopback.id, channelCount: 1, sampleRate: 16000 })
    → system audio stream (WASAPI loopback)
  naudiodon.AudioInput({ deviceId: mic.id, channelCount: 1, sampleRate: 16000 })
    → mic stream
  Both streams chunked into 2s PCM16 buffers
  → sent as binary WebSocket frames to backend /api/v1/cluely/ws

FastAPI backend
  audio_service.py receives binary frames
    → Whisper tiny transcribes (asyncio.to_thread — CPU-bound per ARCHITECTURE.md §4.5)
    → labels speaker: "interviewer" | "user"
    → pushes to context_manager.py
```

IPC channels defined in `electron/ipc/devcore.ts`:
```ts
// Renderer → Main
'devcore:session:start'    payload: SessionStartPayload
'devcore:session:pause'    payload: void
'devcore:session:end'      payload: void
'devcore:interact:enable'  payload: void   // lift click-through
'devcore:interact:disable' payload: void

// Main → Renderer (via webContents.send)
'devcore:suggestion'       payload: { delta: string; done: boolean }
'devcore:transcript'       payload: { speaker: 'interviewer' | 'user'; text: string }
'devcore:status'           payload: { state: 'listening' | 'thinking' | 'paused'; latencyMs: number }
'devcore:error'            payload: { code: string; message: string }
```

---

## 7. WebSocket Message Protocol

All frames between Electron main process and FastAPI backend at `/api/v1/cluely/ws`.

**Authentication:** JWT token sent as the first JSON message after connection:
```json
{ "type": "auth", "token": "<access_token>" }
```
Backend validates the JWT via the existing `security.py` before processing any subsequent frames. Unauthenticated connections are closed with code 4001 after 3s.

**Client → Server frames:**

```jsonc
// Session lifecycle
// New session: generate fresh UUID
{ "type": "session_start", "session_id": "<uuid>", "context": { "job_title": "...", "company": "...", "resume_text": "...", "jd_text": "...", "files": ["<path>"] } }
// Reconnect to existing session: re-send session_start with the SAME session_id.
// Server detects existing Redis key cluely:session:{id}:state and resumes rather than resetting.
// Context field is ignored on resume — server uses stored context from Redis.
{ "type": "session_pause" }
{ "type": "session_end" }

// Audio (binary frame — no JSON wrapper)
// Binary layout: 3 bytes header + N bytes PCM
//   Byte 0:       stream_id  — uint8  (0x01=mic, 0x02=system)
//   Bytes 1–2:    chunk_seq  — uint16 big-endian, wraps at 65535
//   Bytes 3–N:    PCM16 mono 16kHz raw samples

// Manual ask
{ "type": "manual_ask", "text": "...", "mode": "hints" | "solve" }
```

**Server → Client frames:**

```jsonc
{ "type": "transcript", "speaker": "interviewer" | "user", "text": "...", "seq": 42 }
{ "type": "suggestion_delta", "delta": "..." }
{ "type": "suggestion_end" }
{ "type": "code_result", "language": "python", "output": "...", "solution": "..." }
{ "type": "status", "state": "listening" | "thinking" | "paused", "latency_ms": 620 }
{ "type": "error", "code": "BERT_UNAVAILABLE" | "LLM_RATE_LIMITED" | "AUDIO_ERROR", "message": "..." }
```

**Streaming error handling:**
- If Gemini Flash 429 or timeout mid-stream: server sends `{"type": "error", "code": "LLM_RATE_LIMITED"}`, client shows last partial suggestion as-is
- If a second BERT trigger fires while a suggestion is streaming: the in-flight stream is cancelled, a new one starts. No queuing.
- WebSocket disconnect: main process reconnects with exponential backoff (500ms, 1s, 2s, max 3 attempts). Session state survives in Redis (TTL=4h).

---

## 8. Sub-Second Response Pipeline

```
t=0ms    Electron sends 2s PCM binary frame
t=150ms  Whisper tiny transcription complete (asyncio.to_thread)
t=160ms  DistilBERT classifies utterance → question detected (10ms, asyncio.to_thread)
t=165ms  RAG retrieves top-3 context chunks from session file index (5ms)
t=165ms  Gemini Flash streaming call initiated with context window
t=465ms  First token received, sent to Electron as suggestion_delta frame
t=465ms  Overlay displays first words — interviewer still finishing sentence
```

DistilBERT model: `distilbert-base-uncased` fine-tuned on SQuAD2 (question detection head). Quantized to INT8 with `torch.quantization`. Inference time ~10ms CPU. Model loaded into memory at session start, not per-request. If model file missing: `BertClassifierError` is raised, session falls back to silence-detection trigger (~800ms added latency, non-fatal).

**Silence-detection fallback** (in `audio_service.py`): compute RMS of the last 500ms of the interviewer stream. When RMS drops below threshold (0.01 normalized) for ≥400ms after a non-silent segment ≥1s, treat as end-of-utterance and trigger the LLM. This lives in `audio_service.py` as `detect_silence(buffer: bytes) -> bool` and is called only when `bert_classifier.py` raises `BertClassifierError` at startup.

500ms cooldown between BERT triggers prevents rapid re-fire on false positives. A second genuine question cancels the in-flight stream and starts fresh (see §7 streaming error handling).

---

## 9. AI Assistance Modes

### 9.1 Interview Mode (automatic)

BERT detects a question → `llm_service.py` calls Gemini Flash with:
- System prompt: role, company, interview context from session setup
- Last 10 transcript exchanges (from Redis rolling buffer)
- Top-3 RAG chunks from session file index
- Instruction: return a single concise talking point (1–2 sentences), not a bullet list

Response streams token-by-token to the overlay via `suggestion_delta` frames.

### 9.2 Technical Exam Mode (on-demand)

Triggered by user typing in the manual input. Two modes selected in the input:

- **Hints** (`mode: "hints"`) — `claude-sonnet-4-6` explains approach, surfaces relevant docs, similar patterns. Does not write the solution.
- **Solve** (`mode: "solve"`) — `claude-sonnet-4-6` writes solution, `code_runner.py` submits to Judge0 API, execution output + solution streamed back.

Judge0 supported languages in v1: Python, JavaScript, TypeScript, Java, C++, Go, Rust. Language auto-detected from exam context or user-specified.

**Judge0 quota exhaustion:** Free tier allows 100 submissions/day. When Judge0 returns HTTP 429 or quota error, `code_runner.py` raises `CodeRunnerError(code="CODE_RUNNER_QUOTA_EXCEEDED")`. The server sends `{"type": "error", "code": "CODE_RUNNER_QUOTA_EXCEEDED", "message": "Daily code execution limit reached. Solution shown without running."}` to the client. The overlay displays the written solution without execution output — the user can copy and run it themselves. No silent failure.

### 9.3 Web Search (LLM tool, silent)

`llm_service.py` exposes `web_search(query: str)` as a tool available to both Gemini Flash and Claude. The LLM calls it automatically when it determines current information is needed. Implemented in `search_service.py`. Not a UI element.

---

## 10. File System Access (LLM tool, silent)

`filesystem_service.py` builds a local embedding index over user-selected directories at session start. Default scope: `~/Documents`, `~/Desktop`. User can expand or restrict scope in Settings.

**On Windows:** There is no OS-enforced permission dialog for file system access in Electron desktop apps. Scope is enforced at the application level — the service only reads from directories the user has explicitly configured in Settings. The index is built in-process and never leaves the machine except for text excerpts passed as LLM context.

**Privacy note:** File content is passed to Gemini Flash or Claude Sonnet (external APIs) as context when relevant. This is disclosed to the user at onboarding. Users can disable file system access entirely in Settings without affecting other overlay functionality.

Index build is async (`asyncio.to_thread`) and non-blocking. The overlay enters a brief "indexing" state during build, shown in the listening pill. A persistent incremental index is stored in `~/.devcore/file_index/` and refreshed only when files change (mtime comparison), avoiding full rebuild on subsequent sessions.

---

## 11. Overlay UI

### 11.1 States

**Listening (no suggestion yet)**
Minimal pill at top-center: `● DEVCORE | ▁▃▅▃▁ listening...` with animated waveform.

**Suggestion active**
Card expands from pill. Layout (stacked):
1. Header: `DEVCORE · 0.6s · [Mic+System ▾] · [transcript icon] · [⏸ Pause] · [■ End]`
2. Suggestion row: `▸ [streaming suggestion text]`
3. Full-width input: `⌘/ Ask anything… [send icon]`

**Transcript open**
A separate floating card slides in to the LEFT of the main overlay. Shows rolling conversation labelled `them` / `you` with a blinking cursor on the active speaker. Closed with its own × button or by toggling the transcript icon (which goes active/purple).

**Hidden**
Window exists, nothing visible, fully click-through. `Ctrl+Shift+Space` to restore.

### 11.2 Positioning

Default: top-center. `Ctrl+Shift+Arrow` cycles between top-center, top-left, top-right, bottom-center, bottom-right. Position persisted via `electron-store`.

### 11.3 Frontend Structure

Per ARCHITECTURE.md §3, §5.1, §5.2, §5.3. One component per file, PascalCase. Business logic in hooks, not components.

```
frontend/src/
  components/devcore/
    OverlayShell.tsx         — root, mounts in overlay BrowserWindow
    ListeningPill.tsx        — minimal listening state
    SuggestionCard.tsx       — header + suggestion row + input
    TranscriptCard.tsx       — side transcript floating panel
    SessionSetup.tsx         — pre-session modal (in main window)
    AudioSourcePicker.tsx    — dropdown for mic / system / both
  hooks/
    useOverlaySession.ts     — session lifecycle; calls IPC wrapper, not ipcRenderer directly
    useOverlayPosition.ts    — position state and hotkey movement
  store/
    overlayStore.ts          — Zustand store, shape:
                               {
                                 sessionId: string | null,
                                 state: 'idle'|'listening'|'thinking'|'paused',
                                 suggestion: string,
                                 transcript: TranscriptEntry[],
                                 latencyMs: number,
                                 audioSource: 'mic'|'system'|'both',
                                 transcriptOpen: boolean,
                                 position: OverlayPosition,
                                 error: { code: string; message: string } | null,
                               }
  types/
    devcore.ts               — TranscriptEntry, OverlayPosition, SessionContext, etc.
electron/ipc/
  devcore.ts                 — typed IPC channel definitions (see §6)
```

---

## 12. Backend Structure

Per ARCHITECTURE.md §4.2 (Route → Service → Repository → DB). All files `snake_case`, classes `PascalCase`, routes `/api/v1/cluely/...`.

```
backend/app/
  api/v1/cluely/
    ws.py                    — WebSocket route handler; validates auth, delegates to overlay_service
    __init__.py
  services/cluely/
    overlay_service.py       — orchestrates session lifecycle; calls other services
    audio_service.py         — receives PCM frames, runs Whisper (asyncio.to_thread)
    context_manager.py       — rolling transcript in Redis, question window management
    bert_classifier.py       — DistilBERT INT8, loaded at startup, asyncio.to_thread
    rag_service.py           — all-MiniLM index, incremental build, top-k retrieval
    llm_service.py           — Gemini Flash (streaming) + claude-sonnet-4-6 (on-demand); web_search tool
    code_runner.py           — Judge0 API client; language detection; result parsing
    search_service.py        — SerpAPI / Brave Search wrapper (LLM tool)
    filesystem_service.py    — os.walk + embedding index, scoped to user-configured dirs
    __init__.py
  schemas/cluely.py          — Pydantic schemas: SessionStartRequest, TranscriptEntry, SuggestionResponse
```

Custom exceptions (all in `core/exceptions.py`):
- `OverlaySessionNotFoundError`
- `AudioCaptureError`
- `BertClassifierError` — non-fatal, falls back to silence detection
- `LLMRateLimitedError`
- `CodeRunnerError`

---

## 13. Redis Key Format & TTL

Per ARCHITECTURE.md §6.3. Module prefix is `cluely` (matching ARCHITECTURE.md §1 module name).

| Key | TTL | Content |
|---|---|---|
| `cluely:session:{id}:state` | 4h | Session metadata, context, status |
| `cluely:session:{id}:transcript` | 4h | Rolling list of last 20 TranscriptEntry objects |
| `cluely:session:{id}:suggestion` | 30s | Last in-flight suggestion delta buffer |
| `cluely:rag:{user_id}:index_meta` | 24h | File index mtime map for incremental rebuild |

---

## 14. Cost Model

| Component | Model | Cost/session |
|---|---|---|
| Transcription | Whisper tiny (local) | $0 |
| Question detection | DistilBERT (local) | $0 |
| RAG embeddings | all-MiniLM (local) | $0 |
| Real-time suggestions | Gemini Flash 2.0 | ~$0.03 |
| Manual asks / code | `claude-sonnet-4-6` | ~$0.10–0.20 |
| Web search | SerpAPI/Brave | ~$0.01 |
| Code execution | Judge0 (free tier: 100 calls/day) | $0 (free tier) |
| **Total** | | **~$0.05–0.25/session** |

---

## 15. Testing Requirements

Per ARCHITECTURE.md §8. Target: 80% coverage on all backend services.

| Service | Test approach |
|---|---|
| `audio_service.py` | Unit: mock Whisper with fixture PCM files. Test chunking, speaker labelling. |
| `bert_classifier.py` | Unit: test with sample question/non-question strings. Test fallback on missing model. |
| `rag_service.py` | Unit: test index build, retrieval, incremental refresh. Use temp dir with fixture files. |
| `llm_service.py` | Unit: mock Gemini Flash + Claude SDK. Test streaming delta assembly, rate limit handling, tool call routing. |
| `code_runner.py` | Unit: mock Judge0 HTTP responses. Test language detection, timeout, error parsing. |
| `overlay_service.py` | Integration: test full WebSocket session lifecycle with real Redis. |
| `ws.py` | Integration: test JWT auth enforcement (valid, expired, missing). Test binary frame parsing. |
| Electron IPC | Manual test checklist: `setIgnoreMouseEvents`, `WDA_EXCLUDEFROMCAPTURE` confirmed invisible in OBS. No automated E2E for stealth layer (no headless display). |

---

## 16. Privacy & Security

- **Auth:** JWT passed as first WS frame (code 4001 on failure), per ARCHITECTURE.md §7
- **File access:** Scoped to user-configured directories. Disclosed at onboarding. Disableable in Settings.
- **External LLM calls:** File excerpts and transcript text sent to Gemini and Anthropic APIs. Disclosed at onboarding.
- **No persistence by default:** Transcripts held in Redis (TTL=4h) only. Opt-in PostgreSQL persistence via Settings (future phase — requires Alembic migration).
- **Secrets:** Gemini API key, Judge0 key, SerpAPI key added to `.env.example` and loaded via Pydantic `BaseSettings` per ARCHITECTURE.md §4.6. Never committed.
- **Logging:** No PII in logs. Transcript content never logged. Per ARCHITECTURE.md §10.

---

## 17. ARCHITECTURE.md Updates Required

Before implementation begins, add the following to ARCHITECTURE.md §2 tech stack table:

| Addition | Why |
|---|---|
| `naudiodon` (Node, WASAPI) | Cluely module audio capture |
| `DistilBERT INT8` (Python, local) | Cluely module question detection |
| `all-MiniLM-L6-v2` (Python, local) | Cluely module RAG |
| `Gemini Flash 2.0` (Google API) | Cluely module real-time path only |
| `Judge0 API` | Cluely module code execution |
| `SerpAPI / Brave Search` | Cluely module web search tool |
| `ffi-napi` + `ref-napi` (Node) | Cluely module Win32 stealth call |
| `electron-store` | Overlay position persistence |

---

## 18. Out of Scope (v1)

- macOS / Linux support
- Multi-monitor awareness
- Persistent transcript history / session replay
- Google Calendar / Outlook OAuth (CalDAV only in v1)
- Local Docker code execution (Judge0 only in v1)
- Team / shared sessions
