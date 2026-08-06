# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Developer Core backend.

Build command (run from backend/):
    pyinstaller backend.spec

Output: backend/dist/backend/ — include this entire directory as an
electron-builder extraResource so it lands at resources/backend/ in the
installed app.

NOTE: PyInstaller 6.x removed the cipher parameter entirely.
      Do NOT add cipher= to Analysis, PYZ, or EXE.
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_data_files, collect_submodules

ROOT = Path(SPECPATH)  # = backend/

# ── Collect mediapipe + google.protobuf explicitly ────────────────────────────
# mediapipe has a non-standard layout: .pyd files are not picked up by collect_all.
# We copy the full package directory into datas so that both Python files and
# .pyd C-extensions are placed in _internal/ where they are importable.
import importlib.util as _ilu

def _pkg_dir(pkg_name):
    spec = _ilu.find_spec(pkg_name)
    if not spec:
        return None
    p = Path(spec.origin).parent
    return p if p.exists() else None

_mp_src = _pkg_dir('mediapipe')
_mp_binaries = collect_dynamic_libs('mediapipe') if _mp_src else []
_mp_datas = [(str(_mp_src), 'mediapipe')] if _mp_src else []

_proto_src = _pkg_dir('google.protobuf')
_google_src = _proto_src.parent if _proto_src else None  # google/ namespace dir
_proto_datas = [(str(_google_src), 'google')] if _google_src and _google_src.exists() else []

print(f'[spec] mediapipe src: {_mp_src}')
print(f'[spec] google src: {_google_src}')

# Pre-collect submodules for packages that load submodules via strings at runtime.
# collect_submodules() walks the installed package and returns all importable submodule names.
# This is cheaper than collect_all() (no datas/binaries) but ensures every submodule is frozen.
def _safe_submodules(pkg):
    try:
        return collect_submodules(pkg)
    except Exception as e:
        print(f'[spec] collect_submodules({pkg}) failed: {e}')
        return []

_extra_hidden = (
    _safe_submodules('cryptography')
    + _safe_submodules('passlib')
    + _safe_submodules('sqlalchemy')
    + _safe_submodules('starlette')
    + _safe_submodules('fastapi')
    + _safe_submodules('pydantic')
    + _safe_submodules('pydantic_settings')
    + _safe_submodules('jose')
    + _safe_submodules('email')
    + _safe_submodules('xml')
    + _safe_submodules('docx')
    + _safe_submodules('reportlab')
    + _safe_submodules('httpx')
    + _safe_submodules('httpcore')
    + _safe_submodules('anyio')
    + _safe_submodules('structlog')
    + _safe_submodules('slowapi')
    + _safe_submodules('PIL')
    + _safe_submodules('aiosqlite')
)

a = Analysis(
    [str(ROOT / 'run.py')],
    pathex=[str(ROOT)],
    binaries=_mp_binaries,
    datas=[
        # Include all Python source so uvicorn can import `app.*`
        (str(ROOT / 'app'), 'app'),
        # Kokoro ONNX model files (if downloaded; skip if dir missing)
        *([(str(ROOT / 'models'), 'models')] if (ROOT / 'models').exists() else []),
        # Mediapipe full package directory (includes .pyd C-extensions via datas)
        *_mp_datas,
        # google.protobuf (required by mediapipe's pb2 modules)
        *_proto_datas,
    ],
    hiddenimports=[
        # ── uvicorn internals (all loaded via string at runtime) ──────────
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.http.httptools_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.protocols.websockets.wsproto_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        # ── pydantic / settings ───────────────────────────────────────────
        'pydantic',
        'pydantic.v1',
        'pydantic_settings',
        # ── fastapi / starlette ───────────────────────────────────────────
        'fastapi',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.responses',
        'starlette.requests',
        'starlette.background',
        'starlette.staticfiles',
        'starlette.templating',
        'email_validator',
        # ── SQLAlchemy async + aiosqlite ──────────────────────────────────
        'sqlalchemy.ext.asyncio',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.aiosqlite',
        'sqlalchemy.pool',
        'sqlalchemy.orm',
        'aiosqlite',
        # ── passlib / jose / cryptography ─────────────────────────────────
        'passlib',
        'passlib.handlers',
        'passlib.handlers.bcrypt',
        'passlib.handlers.sha2_crypt',
        'passlib.context',
        'jose',
        'jose.jwt',
        'jose.jws',
        'jose.constants',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.ciphers',
        'cryptography.hazmat.primitives.ciphers.algorithms',
        'cryptography.hazmat.primitives.ciphers.modes',
        'cryptography.hazmat.primitives.hashes',
        'cryptography.hazmat.primitives.hmac',
        'cryptography.hazmat.primitives.padding',
        'cryptography.hazmat.primitives.kdf',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.backends',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.backends.openssl.backend',
        'cryptography.x509',
        # ── HTTP clients ──────────────────────────────────────────────────
        'httpx',
        'httpx._client',
        'anyio',
        'anyio._backends._asyncio',
        'anyio.streams.memory',
        # ── AI/API clients ────────────────────────────────────────────────
        'anthropic',
        'openai',
        # ── other runtime-loaded modules ──────────────────────────────────
        'multipart',
        'python_multipart',
        'slowapi',
        'slowapi.util',
        'slowapi.errors',
        'slowapi.wiring',
        'structlog',
        'structlog.stdlib',
        'huggingface_hub',
        # ── stdlib modules used in app/ (not auto-discovered because app/ is DATA) ──
        'imaplib',
        'smtplib',
        'email',
        'email.mime',
        'email.mime.text',
        'email.mime.multipart',
        'email.mime.base',
        'email.mime.application',
        'email.encoders',
        'xml',
        'xml.etree',
        'xml.etree.ElementTree',
        'fnmatch',
        'shlex',
        'unicodedata',
        'wave',
        'webbrowser',
        # ── third-party packages used in app/ ─────────────────────────────
        'pandas',
        'pandas.core',
        'docx',
        'docx.oxml',
        'docx.shared',
        # ── PDF / document generation ─────────────────────────────────────
        'reportlab',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        'reportlab.platypus',
        'reportlab.pdfgen',
        'pdfplumber',
        # ── python-docx ───────────────────────────────────────────────────
        'docx',
        'docx.oxml',
        # ── other app deps ────────────────────────────────────────────────
        'PIL',
        'PIL.Image',
        'numpy',
        'numpy._core',
        'numpy._core._exceptions',
        'numpy._core._multiarray_umath',
        'numpy._core._methods',
        'numpy._core._dtype',
        'numpy._core._dtype_ctypes',
        'numpy._core._internal',
        'numpy._core._type_aliases',
        'numpy._core._ufunc_config',
        'numpy._core.multiarray',
        'numpy._core.numeric',
        'numpy._core.fromnumeric',
        'numpy._core.arrayprint',
        'numpy._core.getlimits',
        'numpy._core.shape_base',
        'numpy._core.defchararray',
        'numpy._core.einsumfunc',
        'numpy._core.function_base',
        'numpy.lib',
        'numpy.lib.stride_tricks',
        'numpy.lib.index_tricks',
        'httpx',
        'httpcore',
        'cv2',
        'mss',
        'deepgram',
        'caldav',
        'keybert',
        # ── collected submodules (packages with string-based import at runtime) ──
        *_extra_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # These packages pull in Chromium — exclude to keep size manageable.
        # Job scraper will still work IF the user installs Playwright browsers separately.
        # Run once after first install: `playwright install chromium`
        'playwright',
        'nodriver',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

# ── Collect data files for packages that use pkg_resources / importlib ────────
# Each collect_all returns (binaries, datas, hiddenimports).
# ctranslate2 is required by faster_whisper at runtime (DLLs must be present).
def _to_3tuple(entry, default_typecode='DATA'):
    """Normalise a collect_all entry to a 3-tuple (src, dest, typecode)."""
    if len(entry) == 3:
        return entry
    return (entry[0], entry[1], default_typecode)

def _safe_collect(pkg):
    """
    collect_all wrapper that normalises all entries to 3-tuples.

    PyInstaller 6.x requires every entry in a.binaries and a.datas to be
    a 3-tuple (src, dest, typecode). Some hooks (e.g. mediapipe) return
    2-tuples (src, dest). We:
      - Promote 2-tuple bins  → (src, dest, 'BINARY')  → a.binaries
      - Promote 2-tuple datas → (src, dest, 'DATA')    → a.datas
      - Drop any non-tuple or mis-sized entries (and log them).
    Additionally, mediapipe's hook puts .py source files into its 'bins'
    list. To avoid linker warnings we move those (identified by extension)
    to datas as 'DATA'.
    """
    try:
        _bins, _datas, _hidden = collect_all(pkg)
    except Exception as e:
        print(f'[spec] skipping {pkg}: {e}')
        return [], [], []

    good_bins, extra_datas = [], []
    for x in _bins:
        if not isinstance(x, tuple) or len(x) not in (2, 3):
            print(f'[spec] {pkg}: dropping malformed bin entry {x!r}')
            continue
        src = x[0]
        dest = x[1]
        # Move Python source files that ended up in binaries → datas
        if src.endswith(('.py', '.pyi', '.pyx', '.txt', '.json', '.tflite', '.tfile')):
            extra_datas.append((src, dest, 'DATA'))
        else:
            good_bins.append((src, dest, 'BINARY') if len(x) == 2 else x)

    norm_datas = []
    for x in _datas:
        if not isinstance(x, tuple) or len(x) not in (2, 3):
            print(f'[spec] {pkg}: dropping malformed data entry {x!r}')
            continue
        norm_datas.append(_to_3tuple(x, 'DATA'))

    return good_bins, norm_datas + extra_datas, _hidden

for pkg in [
    # mediapipe handled separately above (non-standard layout)
    'sentence_transformers',
    'faster_whisper',
    'ctranslate2',       # required by faster_whisper — ships large ONNX/CUDA DLLs
    'spacy',
    'kokoro_onnx',
    'resemblyzer',
    'semble',
    # ── standard app dependencies with data files ─────────────────────────
    'reportlab',
    'pdfplumber',
    'anthropic',
    'openai',
    'httpx',
    'deepgram',
    'caldav',
    'keybert',
    'sklearn',
    'PIL',
    'cv2',
    'mss',
    # ── numpy — must collect_all to get C extension DLLs ─────────────────
    'numpy',
]:
    _bins, _datas, _hidden = _safe_collect(pkg)
    a.binaries        += _bins
    a.datas           += _datas
    a.hiddenimports   += _hidden

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir mode — DLLs live alongside the exe
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX can break native extensions
    console=True,            # keep console for log output (hidden in production via Electron)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='backend',          # output to dist/backend/
)
