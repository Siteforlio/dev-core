"""
PyInstaller entry point for the Developer Core backend.

Sets DATABASE_URL from DEVCORE_USER_DATA env var (passed by Electron in
production) before any app module is imported, so pydantic-settings picks
it up as an env override (env vars beat .env file).
"""
import os
import sys

# ── Resolve user-data DB path (production only) ──────────────────────────────
_user_data = os.environ.get('DEVCORE_USER_DATA', '')
if _user_data:
    _db = os.path.join(_user_data, 'devcore.db')
    os.environ.setdefault('DATABASE_URL', f'sqlite+aiosqlite:///{_db}')

# ── When frozen by PyInstaller, sys._MEIPASS is the extraction folder ─────────
# Add it to sys.path so `app.*` imports resolve correctly.
if getattr(sys, 'frozen', False):
    sys.path.insert(0, sys._MEIPASS)  # type: ignore[attr-defined]

import uvicorn

if __name__ == '__main__':
    uvicorn.run(
        'app.main:app',
        host='127.0.0.1',
        port=8000,
        log_level='info',
    )
