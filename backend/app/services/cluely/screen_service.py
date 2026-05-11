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
import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_VISION_MODEL = "deepseek-vl2"
_BASE         = "https://api.deepseek.com"
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

    async def understand(self, base64_png: str, question: str = "") -> str:
        """
        Send a screenshot to DeepSeek Vision and return its description.

        question — optional specific question to ask about the screen.
        If empty, the model gives a general description of what's visible.
        """
        if not base64_png:
            return ""

        if not settings.deepseek_api_key:
            logger.warning("[screen] No DeepSeek API key — vision disabled")
            return ""

        prompt = question.strip() if question.strip() else (
            "Describe exactly what is visible on this screen. "
            "List all open applications, windows, browser tabs, text content, "
            "and any other notable UI elements you can see. Be specific and thorough."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_png}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        body = {
            "model": _VISION_MODEL,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.2,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(f"{_BASE}/chat/completions", json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("[screen] vision API call failed: %s", exc)
            # Fall back to empty — caller handles gracefully
            return ""

    async def capture_and_extract(self, monitor: int = 1, question: str = "") -> str:
        """
        Convenience: capture the screen and understand it with vision.
        question is forwarded to the model as the specific thing to look for.
        """
        b64 = await self.capture_base64(monitor)
        if not b64:
            return ""
        return await self.understand(b64, question=question)

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
