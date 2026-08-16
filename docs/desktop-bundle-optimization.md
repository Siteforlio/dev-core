# Desktop Bundle Optimization: Reducing a 1.7 GB Electron + Python App to 1.1 GB

## Context

Developer Core is a desktop application built with **Electron** (TypeScript frontend) and a **FastAPI** backend bundled via **PyInstaller**. The app packages ML models and libraries for real-time emotion analysis, speaker diarization, text-to-speech, and AI-assisted interview coaching — all running locally on the user's machine.

The initial packaged installer weighed **1.7 GB installed / 514 MB compressed**, making distribution painful and startup slow. The goal was to significantly reduce bundle size and improve cold-start time without removing any user-facing functionality.

## Problem Analysis

A size audit of the PyInstaller `_internal/` directory revealed the breakdown:

| Package | Size | Actually Used? |
|---------|------|----------------|
| torch | 322 MB | Yes (resemblyzer / speaker diarization) |
| jaxlib | 212 MB | No (optional mediapipe transitive dep) |
| cv2 (OpenCV) | 113 MB | Yes (emotion analysis) |
| mediapipe | 102 MB | Yes (face mesh / emotion detection) |
| llvmlite | 102 MB | No (numba transitive dep, never imported) |
| faiss / faiss_cpu | 72 MB | No (never imported by app code) |
| av.libs | 65 MB | Yes (audio/video processing) |
| scipy | 53 MB | Yes (signal processing) |
| CUDA binaries | ~50 MB | No (desktop app is CPU-only) |

**Key finding:** ~386 MB of the bundle was occupied by packages that were never imported anywhere in the application code — they were pulled in as transitive dependencies by pip and then blindly collected by PyInstaller.

**Second finding:** Heavy ML libraries (mediapipe, OpenCV, numpy, resemblyzer) were imported at module level, forcing Python to load ~400 MB of native libraries during startup before the server could respond to its first request. This caused 15-30 second cold starts.

## Solution: Three-Pronged Approach

### 1. Dead Dependency Elimination (saved ~386 MB installed)

Used `grep` across the entire backend codebase to identify which large packages were actually imported:

```bash
# Zero hits = safe to exclude
grep -r "import jax\|from jax" backend/app/   # 0 results
grep -r "import llvmlite\|import numba" backend/app/   # 0 results
grep -r "import faiss\|from faiss" backend/app/   # 0 results
```

Cross-referenced with `pip show <pkg>` to understand the dependency chain:
- `jaxlib` — required by `jax`, which is an optional dep of `mediapipe` (not used on Windows)
- `llvmlite` — required by `numba`, which nothing imports
- `faiss-cpu` — required by nothing at all

Added these to PyInstaller's `excludes` list in `backend.spec`:

```python
excludes=[
    'jax', 'jaxlib',
    'numba', 'llvmlite',
    'faiss', 'faiss_cpu',
    # ... existing CUDA excludes
]
```

Also added a binary filter to strip any stray `.dll`/`.pyd` files from these packages:

```python
_strip_patterns = ('jaxlib', 'llvmlite', 'faiss',
                   'cublas', 'cudnn', 'cufft', ...)
a.binaries = [b for b in a.binaries
              if not any(p in b[0].lower() for p in _strip_patterns)]
```

### 2. CUDA Binary Stripping (saved ~50 MB)

The desktop app runs CPU-only inference, but PyInstaller collected CUDA runtime libraries from torch. Added comprehensive excludes:

```python
excludes=[
    'torch.cuda', 'torch.backends.cuda', 'torch.backends.cudnn',
    'triton', 'nvidia', 'nvidia.cuda_runtime', 'nvidia.cublas',
    'nvidia.cudnn', 'nvidia.cufft', 'nvidia.cusparse',
    'nvidia.cusolver', 'nvidia.nccl', 'nvidia.nvjitlink', 'nvidia.nvtx',
]
```

### 3. Lazy-Loading Heavy ML Libraries (improved startup time)

Replaced eager module-level imports with a deferred loading pattern. This doesn't reduce bundle size, but dramatically improves cold-start time — the server starts accepting requests in ~3 seconds instead of 15-30.

**Before (eager):**
```python
import mediapipe as mp
import cv2
import numpy as np

class EmotionService:
    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(...)
```

**After (lazy):**
```python
_mp = None
_cv2 = None
_np = None
_face_mesh = None

def _ensure_loaded():
    global _mp, _cv2, _np, _face_mesh
    if _mp is not None:
        return
    import mediapipe as mp
    import cv2
    import numpy as np
    _mp = mp
    _cv2 = cv2
    _np = np
    _face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True, max_num_faces=1,
        refine_landmarks=True, min_detection_confidence=0.5
    )

class EmotionService:
    def analyze_frame(self, frame_b64: str):
        _ensure_loaded()  # First call loads ~400 MB of native libs
        img = _cv2.imdecode(...)
```

Applied this pattern to four services:
- **EmotionService** — mediapipe, cv2, numpy (~215 MB deferred)
- **OverlayService** — deferred singleton instantiation (prevents chain-loading audio_service → numpy)
- **AudioService** — numpy loaded on first use
- **SpeakerDiarizer** — numpy loaded on first use
- **TTSService** — numpy moved inside synthesis method

**Verification:** Wrote subprocess-isolated tests to ensure no eager loading:

```python
def test_no_eager_mediapipe():
    """Importing app.services.emotion_service must NOT pull in mediapipe."""
    result = subprocess.run(
        [sys.executable, "-c",
         "import app.services.emotion_service; import sys; "
         "assert 'mediapipe' not in sys.modules"],
        capture_output=True, timeout=30
    )
    assert result.returncode == 0
```

## Results

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Installed size | 1.7 GB | 1.1 GB | **-35%** |
| Installer (NSIS compressed) | 514 MB | 433 MB | **-16%** |
| Backend bundle (raw) | 1,425 MB | 1,031 MB | **-28%** |
| Cold-start time | 15-30s | ~3s | **-80%** |
| First ML inference | ~0s (pre-loaded) | ~5s (lazy load) | Acceptable trade-off |

## Architecture Decisions

**Why not remove torch entirely?** Torch (322 MB) is the largest remaining dependency, used by `resemblyzer` for speaker diarization — a core feature. Replacing it would require finding a non-torch speaker embedding model or moving diarization to a cloud API, which conflicts with the local-first architecture.

**Why lazy loading instead of microservices?** Splitting ML services into separate processes would reduce memory per process but increase total disk usage (each process needs its own Python runtime + shared libs). Lazy loading achieves the startup-time goal without the operational complexity.

**Why subprocess-isolated tests?** Python's import system is global — once a module is imported in a test process, it can't be "un-imported." Subprocess isolation ensures each test starts clean, giving accurate verification that imports are truly deferred.

## Tech Stack

- **PyInstaller 6.x** (onedir mode) — Python → native executable bundling
- **electron-builder 26.x** — NSIS installer generation for Windows
- **FastAPI + Uvicorn** — backend HTTP/WebSocket server
- **mediapipe / OpenCV / torch / resemblyzer** — ML inference libraries
