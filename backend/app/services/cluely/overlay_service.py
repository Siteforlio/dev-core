import asyncio, logging, json, time, hashlib
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

BERT_COOLDOWN = 0.5          # seconds between BERT triggers
SUGGESTION_CACHE_TTL = 300   # 5 minutes — skip LLM for identical questions
ASK_RATE_LIMIT = 10          # max manual asks per window
ASK_RATE_WINDOW = 60         # seconds
WS_BATCH_CHARS = 50          # buffer this many chars before flushing to WebSocket


async def _empty_list() -> list:
    """Async no-op returning an empty list — used as a parallel placeholder."""
    return []


class OverlayService:
    def __init__(self):
        self._audio = AudioService()
        self._llm = LLMService()
        self._runner = CodeRunner()
        self._last_trigger = 0.0
        # suggestion_cache: {session_id: {question_hash: (timestamp, full_response)}}
        # Keyed by session so the singleton doesn't bleed state across users.
        self._suggestion_cache: dict[str, dict[str, tuple[float, str]]] = {}
        # ask_rate: {session_id: (count, window_start_timestamp)}
        self._ask_rate: dict[str, tuple[int, float]] = {}
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
        # Stash session_id so downstream methods can key caches without
        # threading the ID through every call signature.
        ctx["_session_id"] = sid
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
                # Pass the question text so _stream_suggestion can run RAG
                # in parallel with the transcript window fetch.
                await self._stream_suggestion(ws, ctx_mgr, rag, session_ctx, question_text=result["text"])
        except Exception:
            logger.exception("Audio frame processing error")
            await ws.send_json({"type": "error", "code": "AUDIO_ERROR", "message": "Audio processing failed"})

    async def _stream_suggestion(
        self,
        ws: WebSocket,
        ctx_mgr: ContextManager,
        rag,
        session_ctx: dict,
        question_text: str = "",
    ):
        session_id = session_ctx.get("_session_id", "unknown")
        q_hash = hashlib.md5(question_text.encode()).hexdigest() if question_text else ""

        # --- Deduplication cache check ---
        if q_hash:
            session_cache = self._suggestion_cache.get(session_id, {})
            cached = session_cache.get(q_hash)
            if cached:
                ts, cached_response = cached
                if time.time() - ts < SUGGESTION_CACHE_TTL:
                    logger.debug("Cache hit for question hash %s", q_hash)
                    await ws.send_json({"type": "suggestion_delta", "delta": cached_response})
                    await ws.send_json({"type": "suggestion_end"})
                    return

        await ws.send_json({"type": "status", "state": "thinking", "latency_ms": 0})

        # --- Parallel fetch: transcript window + RAG ---
        # RAG can start immediately because we already have the question text
        # from the BERT trigger — no need to wait for the transcript fetch.
        rag_coro = rag.retrieve(question_text, k=3) if (rag and question_text) else _empty_list()
        transcript, rag_chunks = await asyncio.gather(
            ctx_mgr.get_window(n=10),
            rag_coro,
        )

        t0 = time.monotonic()
        full_response: list[str] = []
        try:
            first = True
            batch: list[str] = []

            async for delta in self._llm.stream_suggestion(
                transcript=transcript,
                context=session_ctx,
                rag_chunks=rag_chunks,
            ):
                if first:
                    latency = round((time.monotonic() - t0) * 1000)
                    await ws.send_json({"type": "status", "state": "listening", "latency_ms": latency})
                    first = False
                batch.append(delta)
                full_response.append(delta)
                # Flush when buffer reaches WS_BATCH_CHARS — reduces frame count
                # by 70–80% vs. sending one token at a time.
                if sum(len(d) for d in batch) >= WS_BATCH_CHARS:
                    await ws.send_json({"type": "suggestion_delta", "delta": "".join(batch)})
                    batch = []

            if batch:
                await ws.send_json({"type": "suggestion_delta", "delta": "".join(batch)})
            await ws.send_json({"type": "suggestion_end"})

            # Store in dedup cache
            if q_hash and full_response:
                if session_id not in self._suggestion_cache:
                    self._suggestion_cache[session_id] = {}
                self._suggestion_cache[session_id][q_hash] = (time.time(), "".join(full_response))

        except LLMRateLimitedError:
            # Fall back to a cached response for the same question if available.
            session_cache = self._suggestion_cache.get(session_id, {})
            cached = session_cache.get(q_hash) if q_hash else None
            if cached:
                _, cached_response = cached
                await ws.send_json({"type": "suggestion_delta", "delta": cached_response})
                await ws.send_json({"type": "suggestion_end"})
            else:
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

        # --- Per-session rate limiting ---
        session_id = session_ctx.get("_session_id", "unknown")
        now = time.time()
        count, window_start = self._ask_rate.get(session_id, (0, now))
        if now - window_start >= ASK_RATE_WINDOW:
            count, window_start = 0, now
        if count >= ASK_RATE_LIMIT:
            await ws.send_json({
                "type": "error",
                "code": "ASK_RATE_LIMITED",
                "message": f"Maximum {ASK_RATE_LIMIT} asks per minute reached. Please wait.",
            })
            return
        self._ask_rate[session_id] = (count + 1, window_start)

        mode = data.get("mode", "hints")
        rag_chunks = await rag.retrieve(text, k=3) if rag else []

        try:
            if mode == "solve":
                # Collect the full solution for Judge0 while streaming to the user.
                solution_parts: list[str] = []
                batch: list[str] = []
                async for delta in self._llm.stream_manual_ask(text, mode=mode, context=session_ctx, rag_chunks=rag_chunks):
                    solution_parts.append(delta)
                    batch.append(delta)
                    if sum(len(d) for d in batch) >= WS_BATCH_CHARS:
                        await ws.send_json({"type": "suggestion_delta", "delta": "".join(batch)})
                        batch = []
                if batch:
                    await ws.send_json({"type": "suggestion_delta", "delta": "".join(batch)})
                await ws.send_json({"type": "suggestion_end"})

                # Execute with Judge0 after solution is assembled
                solution = "".join(solution_parts)
                lang = data.get("language", "python")
                code_result = await self._runner.execute(solution, language=lang)
                await ws.send_json({
                    "type": "code_result",
                    "language": lang,
                    "output": code_result["output"],
                    "solution": solution,
                })
            else:
                # hints / ultra — stream token-by-token
                batch: list[str] = []
                async for delta in self._llm.stream_manual_ask(text, mode=mode, context=session_ctx, rag_chunks=rag_chunks):
                    batch.append(delta)
                    if sum(len(d) for d in batch) >= WS_BATCH_CHARS:
                        await ws.send_json({"type": "suggestion_delta", "delta": "".join(batch)})
                        batch = []
                if batch:
                    await ws.send_json({"type": "suggestion_delta", "delta": "".join(batch)})
                await ws.send_json({"type": "suggestion_end"})

        except CodeRunnerError as e:
            await ws.send_json({"type": "error", "code": e.code, "message": e.message})
        except LLMRateLimitedError:
            await ws.send_json({"type": "error", "code": "LLM_RATE_LIMITED", "message": "Rate limited"})
