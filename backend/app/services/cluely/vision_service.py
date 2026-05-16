"""
vision_service.py — Screenshot analysis using Groq vision (llama-4-scout, free tier).

Design:
- Caller maintains a buffer of up to MAX_BUFFER screenshots per session.
- All buffered images are sent together so Groq sees the full scrolled context.
- System prompt adapts to assessment mode (coding/leetcode vs general).
- Returns a structured result: { text, needs_more, cleared_buffer }
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Literal

from groq import AsyncGroq
from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_BUFFER     = 5          # max screenshots kept per session
BUFFER_TTL_S   = 180        # clear buffer if no screenshot for 3 min
VISION_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"

# Minimum base64 length to be a real image (~1 KB encoded)
MIN_B64_LEN = 1000


def _system_prompt(mode: str | None) -> str:
    if mode == "coding":
        return (
            "You are an expert coding assistant helping a developer during a technical interview. "
            "The user will send one or more screenshots of their screen — these may be consecutive scrolls "
            "of the same LeetCode/coding problem. Analyze ALL screenshots together as one context.\n\n"
            "Your job:\n"
            "1. If you can see a complete problem statement: provide a clear solution approach, "
            "time/space complexity, and working code in the most appropriate language.\n"
            "2. If the screenshots are partial (cut off): say exactly what you can see and ask for more screenshots.\n"
            "3. If you see code the user has already written: review it, identify bugs, suggest improvements.\n"
            "4. If you see test cases or expected outputs: incorporate them into your analysis.\n\n"
            "Be concise. Lead with the approach, then the code. Skip pleasantries."
        )
    elif mode in ("present", "live"):
        return (
            "You are a professional assistant helping during a live presentation or meeting. "
            "The user will send screenshots of their screen. Analyze them and:\n"
            "1. If you see a question or prompt from another person: draft a clear, professional response.\n"
            "2. If you see presentation slides: summarize key points or suggest talking points.\n"
            "3. If you see a form, document, or email: extract what action is needed.\n"
            "4. If the content is unclear or partial: say what you can see and ask for another screenshot.\n\n"
            "Be concise and professional."
        )
    else:
        return (
            "You are an intelligent assistant analyzing screenshots the user has taken of their screen. "
            "These screenshots may be consecutive scrolls of the same content.\n\n"
            "Your job:\n"
            "1. If you see a question, problem, or task: answer it directly and completely.\n"
            "2. If you see partial content (cut off): say what you can read and indicate you need more.\n"
            "3. If you see code: analyze it, find bugs, explain what it does.\n"
            "4. If the screen contains nothing actionable: say so briefly — do not hallucinate tasks.\n\n"
            "Be direct and concise."
        )


class VisionService:
    def __init__(self):
        api_key = settings.groq_api_key
        if not api_key:
            logger.warning("[vision] GROQ_API_KEY not set — vision disabled")
            self._client = None
        else:
            self._client = AsyncGroq(api_key=api_key)

        # Per-session buffers: { session_id: {"images": [...], "last_ts": float} }
        self._buffers: dict[str, dict] = {}

    def add_screenshot(self, session_id: str, image_b64: str) -> int:
        """Add a screenshot to the buffer. Returns new buffer size."""
        now = time.time()
        buf = self._buffers.get(session_id)

        # Evict stale buffer
        if buf and (now - buf["last_ts"]) > BUFFER_TTL_S:
            buf = None

        if buf is None:
            buf = {"images": [], "last_ts": now}
            self._buffers[session_id] = buf

        if len(image_b64) < MIN_B64_LEN:
            logger.warning("[vision] Skipping too-small image (%d chars)", len(image_b64))
            return len(buf["images"])

        buf["images"].append(image_b64)
        buf["last_ts"] = now

        # Keep only last MAX_BUFFER
        if len(buf["images"]) > MAX_BUFFER:
            buf["images"] = buf["images"][-MAX_BUFFER:]

        logger.info("[vision] Buffer[%s] = %d screenshot(s)", session_id, len(buf["images"]))
        return len(buf["images"])

    def clear_buffer(self, session_id: str) -> None:
        self._buffers.pop(session_id, None)
        logger.info("[vision] Buffer[%s] cleared", session_id)

    def buffer_size(self, session_id: str) -> int:
        buf = self._buffers.get(session_id)
        return len(buf["images"]) if buf else 0

    async def analyze(
        self,
        session_id: str,
        mode: str | None = None,
        extra_context: str | None = None,
    ) -> dict:
        """
        Analyze all buffered screenshots for this session.

        Returns:
            {
                "text": str,           # answer / guidance
                "needs_more": bool,    # True if model wants more screenshots
                "buffer_size": int,    # how many images were analyzed
                "cleared": bool,       # True if buffer was cleared after analysis
            }
        """
        if self._client is None:
            return {"text": "", "needs_more": False, "buffer_size": 0, "cleared": False}

        buf = self._buffers.get(session_id)
        if not buf or not buf["images"]:
            return {"text": "No screenshots in buffer.", "needs_more": False, "buffer_size": 0, "cleared": False}

        images = buf["images"]
        n = len(images)
        logger.info("[vision] Analyzing %d screenshot(s) | session=%s | mode=%s", n, session_id, mode)

        # Build content blocks — all images + instruction text
        content: list[dict] = []

        for i, img_b64 in enumerate(images):
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}",
                },
            })

        # Text instruction after images
        context_note = f"\n\nAdditional context: {extra_context}" if extra_context else ""
        if n == 1:
            user_text = f"I've sent 1 screenshot.{context_note} Please analyze it and help me."
        else:
            user_text = (
                f"I've sent {n} screenshots taken consecutively — they may show different parts "
                f"of the same content (e.g. a scrolled problem, multiple tabs).{context_note} "
                f"Analyze them together as one context and help me."
            )
        content.append({"type": "text", "text": user_text})

        try:
            response = await self._client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {"role": "system", "content": _system_prompt(mode)},
                    {"role": "user", "content": content},
                ],
                max_tokens=1024,
                temperature=0.3,
            )
            text = response.choices[0].message.content or ""
        except Exception as e:
            logger.error("[vision] Groq vision error: %s", e)
            return {"text": "", "needs_more": False, "buffer_size": n, "cleared": False}

        # Detect if model is asking for more screenshots
        needs_more = any(phrase in text.lower() for phrase in [
            "need more", "another screenshot", "scroll down", "send more",
            "can't see", "cannot see", "cut off", "partial", "more context",
            "see the rest", "rest of the", "more screenshots",
        ])

        # Clear buffer only if we got a complete answer
        cleared = False
        if not needs_more:
            self.clear_buffer(session_id)
            cleared = True

        logger.info("[vision] Done | needs_more=%s | cleared=%s | len=%d chars", needs_more, cleared, len(text))
        return {"text": text, "needs_more": needs_more, "buffer_size": n, "cleared": cleared}
