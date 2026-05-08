"""
screen_service.py — Screen capture and OCR for the assessment agent.

Captures the primary display (or a specified region) via a headless screenshot
and extracts text using pytesseract.  The Electron layer also has access to
desktopCapturer — this backend service is called when the agent needs to read
what is on screen during an assessment (problem statement, test cases, etc.).

Multi-screen stitching
----------------------
Some assessment problems span 4+ scrolled screens.  The agent calls
`capture_region` multiple times (as Electron scrolls and triggers captures)
and passes all images to `stitch_and_extract` which deduplicates overlapping
text and returns a single clean string.

Dependencies
------------
  mss         — fast cross-platform screenshot (pip install mss)
  pytesseract — OCR wrapper (pip install pytesseract)
  Pillow      — image handling (pip install Pillow)
  tesseract   — system binary (winget install UB-Mannheim.TesseractOCR  /  brew install tesseract)

All are optional — the service degrades gracefully if they are missing.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy dependency loading — non-fatal if not installed
# ---------------------------------------------------------------------------

def _try_import():
    """Return (mss, Image, pytesseract) or (None, None, None)."""
    try:
        import mss                          # type: ignore
        from PIL import Image               # type: ignore
        import pytesseract                  # type: ignore
        return mss, Image, pytesseract
    except ImportError as exc:
        logger.info("[screen] OCR dependencies not available (%s) — screen reading disabled", exc)
        return None, None, None


_mss, _Image, _pytesseract = _try_import()


class ScreenService:
    """
    Capture screenshots and extract text.

    All methods are async — CPU-bound OCR runs in a thread pool via
    asyncio.to_thread so the event loop is never blocked.
    """

    @property
    def available(self) -> bool:
        return _mss is not None

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    async def capture_base64(self, monitor: int = 1) -> str:
        """
        Capture the specified monitor and return a base64-encoded PNG.
        monitor=1 is the primary display (mss convention).
        Returns empty string if mss is unavailable.
        """
        if not self.available:
            return ""

        def _grab() -> bytes:
            with _mss.mss() as sct:
                monitors = sct.monitors
                if monitor >= len(monitors):
                    mon = monitors[1]
                else:
                    mon = monitors[monitor]
                shot = sct.grab(mon)
                img = _Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()

        try:
            png = await asyncio.to_thread(_grab)
            return base64.b64encode(png).decode()
        except Exception as exc:
            logger.warning("[screen] capture failed: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------

    async def extract_text(self, base64_png: str) -> str:
        """
        Run tesseract OCR on a base64-encoded PNG.
        Returns extracted text (may be empty if image is blank or OCR fails).
        """
        if not self.available or not base64_png:
            return ""

        def _ocr() -> str:
            raw = base64.b64decode(base64_png)
            img = _Image.open(io.BytesIO(raw))
            return _pytesseract.image_to_string(img, config="--psm 6")

        try:
            return await asyncio.to_thread(_ocr)
        except Exception as exc:
            logger.warning("[screen] OCR failed: %s", exc)
            return ""

    async def capture_and_extract(self, monitor: int = 1) -> str:
        """Convenience: capture + OCR in one call."""
        b64 = await self.capture_base64(monitor)
        return await self.extract_text(b64)

    # ------------------------------------------------------------------
    # Multi-screen stitching
    # ------------------------------------------------------------------

    async def stitch_and_extract(self, b64_images: list[str]) -> str:
        """
        OCR each image, then deduplicate overlapping lines and return
        a single merged text block.

        Assessment problems that span multiple scrolled screens produce
        images with overlapping content at top/bottom.  We remove
        lines that appeared in the previous image to avoid duplicates.
        """
        if not b64_images:
            return ""

        all_lines: list[str] = []
        seen: set[str] = set()

        for b64 in b64_images:
            text = await self.extract_text(b64)
            for line in text.splitlines():
                stripped = line.strip()
                if stripped and stripped not in seen:
                    seen.add(stripped)
                    all_lines.append(stripped)

        return "\n".join(all_lines)
