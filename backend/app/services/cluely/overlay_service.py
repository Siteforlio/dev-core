import asyncio, logging, json, time
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from app.core.security import decode_token
from app.core.exceptions import BertClassifierError, LLMRateLimitedError, CodeRunnerError
from app.services.cluely.audio_service import AudioService, parse_audio_frame
from app.services.cluely.context_manager import ContextManager
from app.services.cluely.bert_classifier import BertClassifier
from app.services.cluely.rag_service import RagService
from app.services.cluely.llm_service import LLMService
from app.services.cluely.code_runner import CodeRunner
from app.schemas.cluely import TranscriptEntry

logger = logging.getLogger(__name__)
BERT_COOLDOWN = 0.5  # seconds between BERT triggers


class OverlayService:
    def __init__(self):
        self._audio = AudioService()
        self._llm = LLMService()
        self._runner = CodeRunner()
        self._last_trigger = 0.0
        try:
            self._bert = BertClassifier()
            self._use_bert = True
        except BertClassifierError:
            logger.warning("BERT unavailable — using silence detection fallback")
            self._use_bert = False
            self._bert = None

    async def handle(self, ws: WebSocket) -> None:
        await ws.accept()
        ctx_mgr: ContextManager | None = None
        rag: RagService | None = None
        session_ctx: dict = {}

        # Auth gate — first frame must be auth
        try:
            first = await asyncio.wait_for(ws.receive_json(), timeout=3.0)
        except asyncio.TimeoutError:
            await ws.close(code=4001)
            return
        if first.get("type") != "auth":
            await ws.send_json({"type": "error", "code": "AUTH_REQUIRED", "message": "First frame must be auth"})
            await ws.close(code=4001)
            return
        try:
            decode_token(first["token"])
        except Exception:
            await ws.send_json({"type": "error", "code": "AUTH_FAILED", "message": "Invalid token"})
            await ws.close(code=4001)
            return

        try:
            while True:
                msg = await ws.receive()
                if "bytes" in msg:
                    await self._handle_audio(ws, msg["bytes"], ctx_mgr, rag, session_ctx)
                elif "text" in msg:
                    data = json.loads(msg["text"])
                    mtype = data.get("type")
                    if mtype == "session_start":
                        ctx_mgr, rag, session_ctx = await self._start_session(ws, data)
                    elif mtype == "session_pause":
                        if ctx_mgr:
                            await ctx_mgr.set_state("paused")
                        await ws.send_json({"type": "status", "state": "paused", "latency_ms": 0})
                    elif mtype == "session_end":
                        break
                    elif mtype == "manual_ask":
                        await self._handle_manual_ask(ws, data, session_ctx, rag)
        except WebSocketDisconnect:
            logger.debug("Client disconnected")
        except Exception as e:
            logger.exception("Overlay WS error: %s", e)
        finally:
            await ws.close()

    async def _start_session(self, ws: WebSocket, data: dict):
        sid = data["session_id"]
        ctx = data.get("context", {})
        # Import redis lazily to avoid startup errors without Redis configured
        from app.core.cache import get_redis
        r = await get_redis()
        ctx_mgr = ContextManager(redis=r, session_id=sid)
        if not await ctx_mgr.session_exists():
            await ctx_mgr.set_state("listening")
        rag = RagService()
        files = ctx.get("files", [])
        if files:
            task = asyncio.create_task(rag.build_index(files))
            task.add_done_callback(
                lambda t: logger.error("RAG index build failed: %s", t.exception()) if t.exception() else None
            )
        await ws.send_json({"type": "status", "state": "listening", "latency_ms": 0})
        return ctx_mgr, rag, ctx

    async def _handle_audio(self, ws: WebSocket, raw: bytes, ctx_mgr, rag, session_ctx):
        if ctx_mgr is None:
            return
        try:
            stream, seq, pcm = parse_audio_frame(raw)
        except ValueError:
            return
        try:
            speaker = "interviewer" if stream == "system" else "user"
            result = await self._audio.transcribe(pcm, speaker=speaker)
            if not result["text"]:
                return
            entry = TranscriptEntry(speaker=speaker, text=result["text"], seq=seq)
            await ctx_mgr.push_transcript(entry)
            await ws.send_json({"type": "transcript", "speaker": speaker, "text": result["text"], "seq": seq})

            if speaker != "interviewer":
                return

            now = time.monotonic()
            triggered = False
            if self._use_bert and self._bert is not None:
                if now - self._last_trigger > BERT_COOLDOWN:
                    is_q = await self._bert.is_question(result["text"])
                    if is_q:
                        triggered = True

            if triggered:
                self._last_trigger = now
                await self._stream_suggestion(ws, ctx_mgr, rag, session_ctx)
        except Exception:
            logger.exception("Audio frame processing error")
            await ws.send_json({"type": "error", "code": "AUDIO_ERROR", "message": "Audio processing failed"})

    async def _stream_suggestion(self, ws: WebSocket, ctx_mgr: ContextManager, rag, session_ctx: dict):
        await ws.send_json({"type": "status", "state": "thinking", "latency_ms": 0})
        transcript = await ctx_mgr.get_window(n=10)
        rag_chunks = await rag.retrieve(transcript[-1].text if transcript else "", k=3) if rag else []
        t0 = time.monotonic()
        try:
            first = True
            async for delta in self._llm.stream_suggestion(transcript=transcript, context=session_ctx, rag_chunks=rag_chunks):
                if first:
                    latency = round((time.monotonic() - t0) * 1000)
                    await ws.send_json({"type": "status", "state": "listening", "latency_ms": latency})
                    first = False
                await ws.send_json({"type": "suggestion_delta", "delta": delta})
            await ws.send_json({"type": "suggestion_end"})
        except LLMRateLimitedError:
            await ws.send_json({"type": "error", "code": "LLM_RATE_LIMITED", "message": "Rate limited"})
            await ws.send_json({"type": "status", "state": "listening", "latency_ms": 0})
        except Exception:
            logger.exception("Suggestion streaming error")
            await ws.send_json({"type": "error", "code": "LLM_ERROR", "message": "Suggestion failed"})
            await ws.send_json({"type": "status", "state": "listening", "latency_ms": 0})

    async def _handle_manual_ask(self, ws: WebSocket, data: dict, session_ctx: dict, rag):
        text = data.get("text", "")
        if not text:
            await ws.send_json({"type": "error", "code": "INVALID_REQUEST", "message": "text is required"})
            return
        rag_chunks = await rag.retrieve(text, k=3) if rag else []
        try:
            result = await self._llm.manual_ask(
                text,
                mode=data.get("mode", "hints"),
                context=session_ctx,
                rag_chunks=rag_chunks,
            )
            if data.get("mode") == "solve":
                lang = data.get("language", "python")
                code_result = await self._runner.execute(result, language=lang)
                await ws.send_json({
                    "type": "code_result",
                    "language": lang,
                    "output": code_result["output"],
                    "solution": result,
                })
            else:
                await ws.send_json({"type": "suggestion_delta", "delta": result})
                await ws.send_json({"type": "suggestion_end"})
        except CodeRunnerError as e:
            await ws.send_json({"type": "error", "code": e.code, "message": e.message})
