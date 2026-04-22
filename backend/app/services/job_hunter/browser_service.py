# backend/app/services/job_hunter/browser_service.py
"""
BrowserService — stealth Chrome automation via nodriver.

Responsibilities:
  - Launch / reuse a single Chrome instance per task
  - Human-like typing with gaussian keystroke delays
  - File upload helpers
  - Screenshot on error for debugging
  - Detect and handle common bot challenges (Cloudflare, hCaptcha wait)

Used by:
  - ApplyService   → fill and submit job application forms
  - ScrapeService  → LinkedIn / Wellfound / startup boards
  - OutreachService → LinkedIn messaging (future)
  - UpworkService  → proposal submission (future)
"""
import asyncio
import random
import string
import time
from pathlib import Path

import nodriver as uc

# Where to save error screenshots
SCREENSHOTS_DIR = Path(__file__).parent.parent.parent.parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


class BrowserService:
    """
    Manages a single nodriver Chrome session.
    Use as an async context manager:

        async with BrowserService() as browser:
            page = await browser.new_page()
            await browser.goto(page, "https://example.com")
            await browser.type_human(page, 'input[name="email"]', "me@example.com")
    """

    # Default Chrome profile path on Windows
    _DEFAULT_PROFILE = r"C:\Users\Admin\AppData\Local\Google\Chrome\User Data"

    def __init__(self, headless: bool = False, use_profile: bool = False):
        self.headless = headless
        # use_profile=True: launch with the real Chrome profile (Google signed in,
        # cookies, history intact — passes bot verification). Chrome must be closed first.
        self.use_profile = use_profile
        self._browser: uc.Browser | None = None

    async def __aenter__(self):
        args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1280,900",
            "--lang=en-US,en",
            "--accept-lang=en-US,en;q=0.9",
        ]
        kwargs: dict = {"headless": self.headless, "browser_args": args}

        if self.use_profile:
            import os
            profile_dir = os.environ.get("CHROME_PROFILE_DIR", self._DEFAULT_PROFILE)
            # CHROME_PROFILE_NAME: "Default", "Profile 1", "Profile 2", etc.
            profile_name = os.environ.get("CHROME_PROFILE_NAME", "Default")
            args += [
                f"--user-data-dir={profile_dir}",
                f"--profile-directory={profile_name}",
            ]

        self._browser = await uc.start(**kwargs)
        return self

    async def __aexit__(self, *_):
        if self._browser:
            try:
                self._browser.stop()
            except Exception:
                pass
            self._browser = None

    # ── Navigation ───────────────────────────────────────────────────────────

    async def new_page(self) -> uc.Tab:
        """Open a new tab."""
        return await self._browser.get("about:blank")

    async def goto(self, page: uc.Tab, url: str, wait: float = 2.0) -> None:
        """Navigate to URL and wait for load + optional settle time."""
        await page.get(url)
        await asyncio.sleep(wait)

    # ── Human-like interaction ────────────────────────────────────────────────

    async def type_human(self, page: uc.Tab, selector: str, text: str) -> bool:
        """
        Find element by selector and type text with human-like keystroke timing.
        Returns True if element was found and typed into.
        Gaussian delays: mean=80ms, stddev=30ms, min=20ms, occasional 300ms pause.
        """
        try:
            el = await page.find(selector, timeout=5)
            if not el:
                return False
            await el.click()
            await asyncio.sleep(random.uniform(0.1, 0.3))
            for i, char in enumerate(text):
                await el.send_keys(char)
                # Occasional long pause (simulates thinking / hesitation)
                if random.random() < 0.04:
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                else:
                    delay = max(0.02, random.gauss(0.08, 0.03))
                    await asyncio.sleep(delay)
            return True
        except Exception:
            return False

    async def click_human(self, page: uc.Tab, selector: str) -> bool:
        """Click element with small pre-click pause."""
        try:
            el = await page.find(selector, timeout=5)
            if not el:
                return False
            await asyncio.sleep(random.uniform(0.1, 0.4))
            await el.click()
            await asyncio.sleep(random.uniform(0.3, 0.8))
            return True
        except Exception:
            return False

    async def fill_field(self, page: uc.Tab, selector: str, value: str) -> bool:
        """
        Fill a field — uses JS setValue for speed on long text (cover letters etc),
        then dispatches input/change events so React/Vue listeners fire.
        Falls back to type_human for short fields.
        """
        if not value:
            return False
        try:
            el = await page.find(selector, timeout=4)
            if not el:
                return False
            if len(value) > 100:
                # Fast fill via JS for long text
                safe = value.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
                await page.evaluate(
                    f"""
                    (function() {{
                        const el = document.querySelector(`{selector}`);
                        if (!el) return;
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ) || Object.getOwnPropertyDescriptor(
                            window.HTMLTextAreaElement.prototype, 'value'
                        );
                        if (nativeInputValueSetter) nativeInputValueSetter.set.call(el, `{safe}`);
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }})()
                    """
                )
                return True
            else:
                return await self.type_human(page, selector, value)
        except Exception:
            return False

    async def upload_file(self, page: uc.Tab, selector: str, file_path: str) -> bool:
        """Set file input value for resume/CV upload."""
        try:
            el = await page.find(selector, timeout=5)
            if not el:
                return False
            await el.send_file(file_path)
            await asyncio.sleep(0.5)
            return True
        except Exception:
            return False

    async def select_option(self, page: uc.Tab, selector: str, value: str) -> bool:
        """Select a <select> dropdown option by value or text."""
        try:
            await page.evaluate(
                f"""
                (function() {{
                    const sel = document.querySelector(`{selector}`);
                    if (!sel) return;
                    for (const opt of sel.options) {{
                        if (opt.value === `{value}` || opt.text === `{value}`) {{
                            sel.value = opt.value;
                            sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            break;
                        }}
                    }}
                }})()
                """
            )
            return True
        except Exception:
            return False

    # ── Page interrogation ────────────────────────────────────────────────────

    async def get_text(self, page: uc.Tab, selector: str) -> str:
        """Get inner text of element."""
        try:
            el = await page.find(selector, timeout=4)
            if not el:
                return ""
            return (await el.get_html()).strip()
        except Exception:
            return ""

    async def wait_for(self, page: uc.Tab, selector: str, timeout: float = 10.0) -> bool:
        """Wait for element to appear. Returns True if found within timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                el = await page.find(selector, timeout=1)
                if el:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False

    async def current_url(self, page: uc.Tab) -> str:
        try:
            return await page.evaluate("window.location.href")
        except Exception:
            return ""

    # ── Bot challenge helpers ─────────────────────────────────────────────────

    async def wait_past_cloudflare(self, page: uc.Tab, timeout: float = 15.0) -> bool:
        """
        Wait for Cloudflare 'Checking your browser' to pass.
        Returns True once the real page loads.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            url = await self.current_url(page)
            title = await page.evaluate("document.title") or ""
            if "challenge" not in url and "Just a moment" not in title:
                return True
            await asyncio.sleep(1.0)
        return False

    # ── Debugging ─────────────────────────────────────────────────────────────

    async def screenshot(self, page: uc.Tab, name: str = "") -> str:
        """Save a screenshot to SCREENSHOTS_DIR. Returns the file path."""
        ts = int(time.time())
        slug = name or "debug"
        path = SCREENSHOTS_DIR / f"{slug}_{ts}.png"
        try:
            await page.save_screenshot(str(path))
        except Exception:
            pass
        return str(path)
