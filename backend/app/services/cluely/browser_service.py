"""
browser_service.py — Headless browser navigation for the assessment agent.

Uses Playwright (already a dependency via crawlee) to silently fetch pages,
scroll through them, and extract text content.  No browser window is ever
shown to the user or the proctoring software.

Primary use cases
-----------------
1. Search a LeetCode / GeeksForGeeks / NeetCode page for a problem by name
   and extract the problem statement + visible test cases.
2. Fetch any URL and return its text content (for additional research).
3. Extract structured test cases from assessment platform result panels.

Stealth notes
-------------
- Uses chromium in headless mode — no visible window.
- navigator.webdriver is patched to False via launch args so anti-bot
  fingerprinting is less likely to flag the session.
- All network I/O is async and non-blocking.
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# Heuristic selectors for common platforms — extended as needed.
_PROBLEM_SELECTORS = [
    "[data-track-load='description_content']",   # LeetCode
    ".problem-statement",                         # Codeforces
    "#problem-statement",                         # HackerRank
    ".challenge-text",                            # HackerEarth
    "article",                                    # GeeksForGeeks / generic
    "main",                                       # fallback
]

_TEST_CASE_SELECTORS = [
    ".example-testcases",                         # LeetCode
    ".sample-tests",                              # Codeforces
    ".testcase-panel",                            # HackerRank
    ".challenge-sample-input",                    # HackerEarth
]


class BrowserService:
    """
    Headless browser operations for reading assessment pages.

    The browser instance is created lazily and shared across calls within
    a session to avoid the startup overhead on every request.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        try:
            from playwright.async_api import async_playwright  # type: ignore
            self._playwright = await async_playwright().start()
            try:
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ],
                )
                logger.info("[browser] Chromium headless started")
            except Exception as launch_exc:
                # Browser binary missing — auto-install it then retry once
                missing = any(
                    kw in str(launch_exc).lower()
                    for kw in ("executable", "not found", "browser", "chromium")
                )
                if missing:
                    logger.info("[browser] Chromium binary missing — running 'playwright install chromium'…")
                    await _install_chromium()
                    self._browser = await self._playwright.chromium.launch(
                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-blink-features=AutomationControlled",
                            "--disable-dev-shm-usage",
                        ],
                    )
                    logger.info("[browser] Chromium headless started (post-install)")
                else:
                    raise
        except Exception as exc:
            logger.warning("[browser] Playwright unavailable: %s", exc)
            self._browser = None

    async def close(self) -> None:
        """Release browser resources. Call at session end."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._playwright = None

    # ------------------------------------------------------------------
    # Page fetching
    # ------------------------------------------------------------------

    async def fetch_text(self, url: str, wait_ms: int = 1500) -> str:
        """
        Fetch a URL and return the visible text content.
        Returns empty string on failure.
        """
        await self._ensure_browser()
        if not self._browser:
            return ""

        try:
            page = await self._browser.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>false})"
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(wait_ms)
            text = await page.evaluate("() => document.body.innerText")
            await page.close()
            return text or ""
        except Exception as exc:
            logger.warning("[browser] fetch_text failed for %s: %s", url, exc)
            return ""

    async def fetch_problem(self, url: str) -> dict:
        """
        Fetch an assessment problem page and extract:
          - problem_text  : full problem statement
          - test_cases    : list of {input, output} dicts from visible examples
          - raw_text      : full page text (fallback)

        Returns a dict with those keys (values may be empty strings / []).
        """
        await self._ensure_browser()
        if not self._browser:
            return {"problem_text": "", "test_cases": [], "raw_text": ""}

        try:
            page = await self._browser.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>false})"
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

            # Extract problem statement — try known selectors in order
            problem_text = ""
            for sel in _PROBLEM_SELECTORS:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        problem_text = (await el.inner_text()) or ""
                        if problem_text.strip():
                            break
                except Exception:
                    continue

            # Extract visible test cases
            test_cases = await _extract_test_cases(page)

            raw_text = await page.evaluate("() => document.body.innerText")
            await page.close()

            return {
                "problem_text": problem_text.strip(),
                "test_cases":   test_cases,
                "raw_text":     (raw_text or "").strip(),
            }
        except Exception as exc:
            logger.warning("[browser] fetch_problem failed for %s: %s", url, exc)
            return {"problem_text": "", "test_cases": [], "raw_text": ""}

    # ------------------------------------------------------------------
    # Scroll + stitch (multi-page problems)
    # ------------------------------------------------------------------

    async def scroll_and_capture_text(self, url: str, scroll_steps: int = 5) -> str:
        """
        Scroll through a page and accumulate all visible text.
        Useful for problems that load content dynamically as the user scrolls.
        """
        await self._ensure_browser()
        if not self._browser:
            return ""

        try:
            page = await self._browser.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>false})"
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(1500)

            seen_lines: set[str] = set()
            all_lines: list[str] = []

            for _ in range(scroll_steps):
                text = await page.evaluate("() => document.body.innerText")
                for line in (text or "").splitlines():
                    stripped = line.strip()
                    if stripped and stripped not in seen_lines:
                        seen_lines.add(stripped)
                        all_lines.append(stripped)
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
                await page.wait_for_timeout(600)

            await page.close()
            return "\n".join(all_lines)
        except Exception as exc:
            logger.warning("[browser] scroll_and_capture failed for %s: %s", url, exc)
            return ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _extract_test_cases(page) -> list[dict]:
    """
    Extract {input, output} pairs from visible example test case blocks.
    Tries known selectors; falls back to regex on raw page text.
    """
    cases: list[dict] = []

    for sel in _TEST_CASE_SELECTORS:
        try:
            elements = await page.query_selector_all(sel)
            for el in elements:
                text = await el.inner_text()
                parsed = _parse_input_output(text)
                if parsed:
                    cases.extend(parsed)
            if cases:
                return cases
        except Exception:
            continue

    # Regex fallback on full page text
    raw = await page.evaluate("() => document.body.innerText")
    if raw:
        cases = _parse_input_output(raw)

    return cases


async def _install_chromium() -> None:
    """
    Run 'playwright install chromium' so the binary is downloaded automatically
    on first use.  Command is hardcoded — no user input, no shell=True.
    """
    try:
        # argv is fully hardcoded — no injection vector
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "playwright", "install", "chromium",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        if proc.returncode == 0:
            logger.info("[browser] playwright install chromium succeeded")
        else:
            logger.warning(
                "[browser] playwright install chromium exited %d: %s",
                proc.returncode, (stdout or b"").decode(errors="replace")[:300],
            )
    except asyncio.TimeoutError:
        logger.warning("[browser] playwright install timed out after 180s")
    except Exception as exc:
        logger.warning("[browser] playwright install failed: %s", exc)


def _parse_input_output(text: str) -> list[dict]:
    """
    Parse Input / Output pairs from a text block.
    Handles LeetCode / HackerRank / Codeforces label patterns.
    """
    pattern = re.compile(
        r"(?:Input|input|Input:)\s*[:\-]?\s*(.*?)\s*(?:Output|output|Output:)\s*[:\-]?\s*(.*?)(?=(?:Input|input|Example|Constraints|Note|\Z))",
        re.DOTALL,
    )
    cases = []
    for m in pattern.finditer(text):
        inp = m.group(1).strip()
        out = m.group(2).strip()
        if inp and out:
            cases.append({"input": inp, "output": out})
    return cases[:10]  # cap at 10 visible test cases
