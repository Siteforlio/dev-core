"""
serve.py — Start uvicorn on Windows without Ctrl+C hangs.

Usage:
  python serve.py              # no reload (default) — Ctrl+C works instantly
  python serve.py --reload     # WatchFiles reload — Ctrl+C works via subprocess wrapper
  python serve.py --port 8001

Architecture:
  Without --reload: uvicorn runs directly; single process; Ctrl+C is instant.
  With --reload:    we run uvicorn as a subprocess in a NEW process group so
                    Ctrl+C only goes to US, not the child. We forward shutdown
                    via CTRL_BREAK_EVENT and enforce a 5-second hard kill.
"""
import sys
import os

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    os.environ["PYTHONASYNCIODEBUG"] = "0"

os.environ["UVICORN_ACCESS_LOG"] = "1"

import argparse
import signal
import uvicorn

# ── Argument parsing ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--reload", action="store_true", default=False,
                    help="Enable WatchFiles auto-reload (handled via subprocess wrapper on Windows)")
parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()


# ── Reload mode: subprocess wrapper keeps signal control in this process ──────
if args.reload and sys.platform == "win32":
    import subprocess
    import ctypes

    cmd = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0",
        "--port", str(args.port),
        "--reload",
        "--loop", "asyncio",
        "--log-level", "info",
        "--access-log",
        "--timeout-graceful-shutdown", "3",
    ]

    proc = subprocess.Popen(
        cmd,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # isolate from our Ctrl+C
    )

    def _shutdown_child(sig, frame):
        print("\n  Shutting down...", flush=True)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            # Send Ctrl+Break to the child process group so uvicorn shuts down gracefully
            ctypes.windll.kernel32.GenerateConsoleCtrlEvent(1, proc.pid)
            proc.wait(timeout=5)
        except Exception:
            pass
        if proc.poll() is None:
            proc.kill()
        os._exit(0)

    signal.signal(signal.SIGINT, _shutdown_child)
    proc.wait()
    os._exit(0)


# ── No-reload mode (default): simple, direct, Ctrl+C always works ─────────────
def _force_exit(sig, frame):
    """Ctrl+C — hard exit after uvicorn's own handler runs."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    print("\n  Shutting down...", flush=True)
    raise KeyboardInterrupt


signal.signal(signal.SIGINT, _force_exit)

uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=args.port,
    reload=args.reload,
    timeout_graceful_shutdown=3,
    loop="asyncio",
    access_log=True,
    log_level="info",
    use_colors=True,
)

os._exit(0)  # ensure exit even if uvicorn returns without calling sys.exit
