"""
Standalone LinkedIn scraper entry point.

Invoked as a subprocess by scraper_service.py so that nodriver runs in its own
fresh Python process with the default Windows ProactorEventLoop — which supports
both asyncio.create_subprocess_exec (needed by nodriver to launch Chrome) AND
the asyncio I/O primitives nodriver uses internally.

Usage (called by scraper_service, not directly):
    python linkedin_runner.py <json_input_b64>

Input JSON (base64-encoded on argv[1]):
    {
        "email": "...",           # optional
        "password": "...",        # optional
        "session_cookie": "...",  # optional
        "search_term": "...",
        "location": "...",
        "remote_only": true/false,
        "max_jobs": 150
    }

Output: newline-delimited JSON on stdout.
    Each line is one of:
        {"type": "log", "msg": "..."}
        {"type": "jobs", "jobs": [...]}
        {"type": "error", "msg": "..."}
"""
import asyncio
import base64
import json
import sys
from pathlib import Path

# Ensure backend root is on sys.path so `from app.*` imports resolve
_backend_root = str(Path(__file__).parent.parent.parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)


async def main():
    raw = base64.b64decode(sys.argv[1].encode()).decode()
    params = json.loads(raw)

    from app.services.job_hunter.linkedin_scraper import LinkedInScraper

    logs: list[str] = []

    async def pub(msg: str):
        out = json.dumps({"type": "log", "msg": msg})
        print(out, flush=True)

    scraper = LinkedInScraper(
        email=params.get("email"),
        password=params.get("password"),
        session_cookie=params.get("session_cookie"),
    )

    jobs = await scraper.scrape(
        search_term=params["search_term"],
        location=params.get("location", ""),
        remote_only=params.get("remote_only", False),
        max_jobs=params.get("max_jobs", 150),
        publish_fn=pub,
    )

    print(json.dumps({"type": "jobs", "jobs": jobs}), flush=True)


if __name__ == "__main__":
    # On Windows, force SelectorEventLoop — nodriver 0.4x uses subprocess.Popen
    # (not asyncio.create_subprocess_exec) to launch Chrome, so SelectorEventLoop
    # works fine and avoids ProactorEventLoop's missing add_reader/add_writer support
    # which breaks websocket-based CDP communication.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
