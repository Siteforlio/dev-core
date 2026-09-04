"""
screen_service.py — Screen capture with DeepSeek Vision understanding.

Captures the primary display via mss (fast cross-platform screenshot) and
sends the image directly to DeepSeek's vision model for understanding.
This replaces the old Tesseract OCR pipeline which struggled with dark UIs,
small text, and anything rendered by a GPU (browsers, Electron apps).

DeepSeek Vision reads the screenshot like a human — it can count tabs,
read UI elements, describe layout, and answer questions about what's visible.
It uses the same API key and endpoint as the text model.

Dependencies
------------
  mss    — fast cross-platform screenshot (pip install mss)
  Pillow — image resizing before sending (pip install Pillow)
  httpx  — already a project dependency

mss and Pillow are optional — the service degrades gracefully if missing.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging


logger = logging.getLogger(__name__)

_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
_TIMEOUT      = 45.0

# Resize screenshots to this width before sending — reduces tokens ~4x
# while keeping enough detail for the model to read UI elements clearly.
_MAX_WIDTH = 1280


def _try_import_capture():
    try:
        import mss               # type: ignore
        from PIL import Image    # type: ignore
        return mss, Image
    except ImportError as exc:
        logger.info("[screen] mss/Pillow not available (%s) — capture disabled", exc)
        return None, None


_mss, _Image = _try_import_capture()


class ScreenService:
    """
    Capture the screen and understand it with DeepSeek Vision.

    capture_and_extract(question) → takes a screenshot, sends it to the
    vision model with an optional question, returns a descriptive string.
    """

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    @property
    def available(self) -> bool:
        return _mss is not None

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    async def capture_base64(self, monitor: int = 1) -> str:
        """
        Capture the specified monitor and return a base64-encoded PNG,
        resized to _MAX_WIDTH to reduce token cost.
        Returns empty string if mss is unavailable.
        """
        if not self.available:
            return ""

        def _grab() -> bytes:
            with _mss.mss() as sct:
                monitors = sct.monitors
                mon = monitors[monitor] if monitor < len(monitors) else monitors[1]
                shot = sct.grab(mon)
                img = _Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                # Resize to reduce tokens while keeping legibility
                if img.width > _MAX_WIDTH:
                    ratio = _MAX_WIDTH / img.width
                    new_h = int(img.height * ratio)
                    img = img.resize((_MAX_WIDTH, new_h), _Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                return buf.getvalue()

        try:
            png = await asyncio.to_thread(_grab)
            return base64.b64encode(png).decode()
        except Exception as exc:
            logger.warning("[screen] capture failed: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Vision understanding
    # ------------------------------------------------------------------

    async def understand(self, base64_png: str, anthropic_api_key: str, question: str = "") -> str:
        """
        Send a screenshot to Claude Haiku vision and return its description.

        question — optional specific question to ask about the screen.
        If empty, the model gives a general description of what's visible.
        """
        if not base64_png:
            return ""

        if not anthropic_api_key:
            logger.warning("[screen] No Anthropic API key — vision disabled")
            return ""

        prompt = question.strip() if question.strip() else (
            "Describe exactly what is visible on this screen. "
            "List all open applications, windows, browser tabs, text content, "
            "and any other notable UI elements you can see. Be specific and thorough."
        )

        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                system="You are a screen analysis assistant. Describe what you see accurately and concisely.",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": base64_png,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                max_tokens=1024,
            )
            return response.content[0].text if response.content else ""
        except Exception as exc:
            logger.warning("[screen] Anthropic vision call failed: %s", exc)
            return ""

    async def capture_and_extract(self, monitor: int = 1, question: str = "") -> str:
        """
        Convenience: capture the screen and understand it with vision.
        question is forwarded to the model as the specific thing to look for.
        """
        b64 = await self.capture_base64(monitor)
        if not b64:
            return ""
        return await self.understand(b64, self._api_key, question=question)

    # ------------------------------------------------------------------
    # Multi-screen stitching (kept for assessment agent compatibility)
    # ------------------------------------------------------------------

    async def stitch_and_extract(self, b64_images: list[str]) -> str:
        """
        Understand multiple screenshots and merge into a single text block.
        Used by the assessment agent when a problem spans multiple screens.
        """
        if not b64_images:
            return ""
        results = []
        for b64 in b64_images:
            text = await self.understand(b64)
            if text:
                results.append(text)
        return "\n\n---\n\n".join(results)
