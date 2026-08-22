"""
vision_service.py — Screenshot analysis using Claude Haiku (Anthropic).

Design:
- Caller maintains a buffer of up to MAX_BUFFER screenshots per session.
- All buffered images are sent together so the model sees the full scrolled context.
- System prompt adapts to assessment mode (coding/leetcode vs general).
- Session context (role, resume, JD, transcript) is injected so the AI can
  give personalised, situation-aware responses.
- stream_analyze() yields token deltas for real-time display.
- Images are compressed (resized + JPEG) before sending to cut upload time.
- Only the screenshot/vision path uses Anthropic — all other LLM calls use DeepSeek.
"""
from __future__ import annotations

import base64
import io
import logging
import time
from typing import AsyncGenerator

import anthropic
from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_BUFFER     = 5          # max screenshots kept per session
BUFFER_TTL_S   = 180        # clear buffer if no screenshot for 3 min
VISION_MODEL   = "claude-haiku-4-5-20251001"

# Minimum base64 length to be a real image (~1 KB encoded)
MIN_B64_LEN = 1000

# Image compression settings
_MAX_WIDTH  = 1280   # resize wider images to this
_JPEG_QUALITY = 72   # JPEG quality — good enough for text/code on screen


def _compress_image(b64_png: str) -> tuple[str, str]:
    """
    Compress a base64 PNG screenshot → smaller JPEG.
    Returns (base64_data, media_type).
    Falls back to the original PNG on any error.
    """
    try:
        from PIL import Image
        raw = base64.b64decode(b64_png)
        img = Image.open(io.BytesIO(raw))

        # Resize if wider than _MAX_WIDTH (preserve aspect ratio)
        if img.width > _MAX_WIDTH:
            ratio = _MAX_WIDTH / img.width
            img = img.resize(
                (int(img.width * ratio), int(img.height * ratio)),
                Image.LANCZOS,
            )

        # Convert to RGB (JPEG doesn't support alpha)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
        compressed = base64.b64encode(buf.getvalue()).decode()
        logger.debug(
            "[vision] compressed %d→%d chars (%.0f%% reduction)",
            len(b64_png), len(compressed),
            (1 - len(compressed) / len(b64_png)) * 100,
        )
        return compressed, "image/jpeg"
    except Exception as e:
        logger.warning("[vision] compression failed, using original PNG: %s", e)
        return b64_png, "image/png"


def _system_prompt(mode: str | None) -> str:
    base = (
        "You are the user. Not a coach. Not an assistant. You ARE them.\n\n"
        "When you see an interview question on screen: write the answer they should say out loud, "
        "word for word, in first person, using their actual background from the context provided. "
        "Start immediately with the answer — no intro, no 'here's what to say', no bullet points, "
        "no coaching tips, no descriptions of what's on screen. "
        "Just the words they speak into the mic.\n\n"
        "Example of WRONG output: 'You're on question 2. The question asks about the hardest problem. "
        "You should talk about DigiLaw and hit Start Recording.'\n\n"
        "Example of RIGHT output: 'The hardest problem I've solved recently was building the real-time "
        "consultation system at DigiLaw. We needed court-defensible audit logs for legal proceedings — "
        "every message timestamped, immutable, tied to a verified session. I built it on ActionCable "
        "WebSockets with timestamped message persistence, and it now handles concurrent consultations "
        "across thousands of users with zero disputes. The constraint made it harder but also made me "
        "think like an engineer who ships for real consequences, not just demos.'\n\n"
        "If the screen shows code: review it directly, in first person if relevant. "
        "If the screen is genuinely blank or unreadable: say so in one sentence, nothing more. "
        "No lists. No headers. No meta-commentary. Ever.\n\n"
    )
    if mode == "coding":
        return base + (
            "For coding problems: give the approach and the code. Lead with the solution, not the explanation."
        )
    elif mode in ("present", "live"):
        return base + (
            "For presentations or meetings: give the words to say, confident and natural."
        )
    else:
        return base


def _build_context_note(session_ctx: dict | None) -> str:
    """
    Build a context block from session data so the AI understands who the user
    is and what they're doing before it reads the screen. No size limits —
    pass everything so the AI has full context.
    """
    if not session_ctx:
        return ""

    parts: list[str] = []

    role    = session_ctx.get("job_title") or session_ctx.get("role", "")
    company = session_ctx.get("company", "")
    if role and company:
        parts.append(f"User's role/context: {role} at {company}")
    elif role:
        parts.append(f"User's role: {role}")
    elif company:
        parts.append(f"Company: {company}")

    resume = session_ctx.get("resume_text", "")
    if resume:
        parts.append(f"Resume:\n{resume}")

    jd = session_ctx.get("jd_text", "")
    if jd:
        parts.append(f"Job description:\n{jd}")

    extra = session_ctx.get("extra_context", "")
    if extra:
        parts.append(f"Loaded context files (CV, notes, etc.):\n{extra}")

    # Recent transcript — last 8 utterances
    transcript_buf = session_ctx.get("_transcript_buf", [])
    if transcript_buf:
        recent = transcript_buf[-8:]
        lines = [f"{e.speaker.upper()}: {e.text}" for e in recent if hasattr(e, "speaker")]
        if lines:
            parts.append("Recent conversation:\n" + "\n".join(lines))

    # Previous screenshot responses — so the AI doesn't repeat the same answer
    prev_responses = session_ctx.get("_vision_responses", [])
    if prev_responses:
        parts.append(
            "IMPORTANT — You already gave these answers earlier in this session. "
            "Do NOT repeat the same story or advice. Give a fresh, different response:\n"
            + "\n---\n".join(prev_responses)
        )

    if not parts:
        return ""

    return "\n\n---\nSession context:\n" + "\n\n".join(parts)


class VisionService:
    def __init__(self):
        api_key = settings.anthropic_api_key
        if not api_key:
            logger.warning("[vision] ANTHROPIC_API_KEY not set — vision disabled")
            self._client = None
        else:
            self._client = anthropic.AsyncAnthropic(api_key=api_key)

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
        session_ctx: dict | None = None,
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

        # Build content blocks — Anthropic format: images first, then the text prompt
        content: list[dict] = []

        for img_b64 in images:
            compressed, media_type = _compress_image(img_b64)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": compressed,
                },
            })

        # Build user message: basic instruction + all available context
        context_note = _build_context_note(session_ctx)
        if not context_note and extra_context:
            context_note = f"\n\nAdditional context: {extra_context}"

        if n == 1:
            user_text = f"I've shared 1 screenshot of my screen.{context_note}\n\nPlease read it and help me."
        else:
            user_text = (
                f"I've shared {n} screenshots taken consecutively — they may show different parts "
                f"of the same content (e.g. a scrolled page, multiple tabs).{context_note}\n\n"
                f"Analyze them together as one context and help me."
            )
        content.append({"type": "text", "text": user_text})

        try:
            response = await self._client.messages.create(
                model=VISION_MODEL,
                system=_system_prompt(mode),
                messages=[{"role": "user", "content": content}],
                max_tokens=1024,
            )
            text = response.content[0].text if response.content else ""
        except Exception as e:
            logger.error("[vision] Anthropic vision error: %s", e)
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

    async def stream_analyze(
        self,
        session_id: str,
        mode: str | None = None,
        extra_context: str | None = None,
        session_ctx: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming version of analyze() — yields token deltas as they arrive.
        Buffer management (needs_more detection, clearing) happens after the
        stream completes via a final metadata yield prefixed with \\x00.
        """
        if self._client is None:
            return

        buf = self._buffers.get(session_id)
        if not buf or not buf["images"]:
            return

        images = buf["images"]
        n = len(images)
        logger.info("[vision] stream_analyze %d screenshot(s) | session=%s", n, session_id)

        t_start = time.time()

        # Build content blocks with compressed images
        content: list[dict] = []
        for img_b64 in images:
            compressed, media_type = _compress_image(img_b64)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": compressed,
                },
            })

        context_note = _build_context_note(session_ctx)
        if not context_note and extra_context:
            context_note = f"\n\nAdditional context: {extra_context}"

        if n == 1:
            user_text = f"I've shared 1 screenshot of my screen.{context_note}\n\nPlease read it and help me."
        else:
            user_text = (
                f"I've shared {n} screenshots taken consecutively — they may show different parts "
                f"of the same content (e.g. a scrolled page, multiple tabs).{context_note}\n\n"
                f"Analyze them together as one context and help me."
            )
        content.append({"type": "text", "text": user_text})

        full_text_parts: list[str] = []
        try:
            async with self._client.messages.stream(
                model=VISION_MODEL,
                system=_system_prompt(mode),
                messages=[{"role": "user", "content": content}],
                max_tokens=1024,
            ) as stream:
                first_token = True
                async for delta in stream.text_stream:
                    if first_token:
                        elapsed = round((time.time() - t_start) * 1000)
                        logger.info("[vision] first token in %dms", elapsed)
                        first_token = False
                    full_text_parts.append(delta)
                    yield delta
        except Exception as e:
            logger.error("[vision] stream error: %s", e)
            return

        full_text = "".join(full_text_parts)
        elapsed_total = round((time.time() - t_start) * 1000)
        logger.info("[vision] stream done in %dms | %d chars", elapsed_total, len(full_text))

        # Buffer management — same logic as non-streaming analyze
        needs_more = any(phrase in full_text.lower() for phrase in [
            "need more", "another screenshot", "scroll down", "send more",
            "can't see", "cannot see", "cut off", "partial", "more context",
            "see the rest", "rest of the", "more screenshots",
        ])
        if not needs_more:
            self.clear_buffer(session_id)
