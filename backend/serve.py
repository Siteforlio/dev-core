"""
serve.py — Start uvicorn with ProactorEventLoop on Windows.

Usage: python serve.py [--reload] [--port 8000]
Replaces: uvicorn app.main:app --reload --port 8000

On Windows, uvicorn's --reload mode ignores asyncio.set_event_loop_policy()
set inside app.main because the reloader runs in a separate process.
Launching via this script sets the policy before uvicorn starts, ensuring
ProactorEventLoop is used in all worker processes (required for subprocess
support in the terminal tool).
"""
import sys
import os

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Also set for child processes spawned by --reload
    os.environ["PYTHONASYNCIODEBUG"] = "0"

import uvicorn

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_true", default=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", dest="reload", action="store_false")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=args.port,
        reload=args.reload,
        timeout_graceful_shutdown=1,
        loop="asyncio",   # forces ProactorEventLoop on Windows via asyncio policy
    )
