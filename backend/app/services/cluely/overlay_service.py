import asyncio, logging, json, time, hashlib
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState
from app.core.security import decode_token
from app.core.exceptions import BertClassifierError, LLMRateLimitedError, CodeRunnerError
from app.services.cluely.audio_service import AudioService, parse_audio_frame
from app.services.cluely.context_manager import ContextManager
from app.services.cluely.bert_classifier import BertClassifier
from app.services.cluely.rag_service import RagService
from app.services.cluely.llm_service import LLMService
from app.services.cluely.code_runner import CodeRunner
from app.services.cluely.summarizer import run_summarizer
from app.schemas.cluely import TranscriptEntry

logger = logging.getLogger(__name__)

BERT_COOLDOWN = 0.5          # seconds between BERT triggers
SUGGESTION_CACHE_TTL = 300   # 5 minutes — skip LLM for identical questions
ASK_RATE_LIMIT = 10          # max manual asks per window
ASK_RATE_WINDOW = 60         # seconds
WS_BATCH_CHARS = 12          # buffer this many chars before flushing to WebSocket


async def _empty_list() -> list:
    """Async no-op returning an empty list — used as a parallel placeholder."""
    return []


async def _safe_send(ws: WebSocket, data: dict) -> bool:
    """Send JSON, returning False silently if the client already disconnected."""
    try:
        if ws.client_state != WebSocketState.CONNECTED:
            return False
        await ws.send_json(data)
        return True
    except (WebSocketDisconnect, RuntimeError, Exception):
        return False


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
        # recent transcripts for dedup: {session_id: [(timestamp, text), ...]}
        self._recent_texts: dict[str, list[tuple[float, str]]] = {}
        self._DEDUP_WINDOW = 4.0   # seconds — suppress identical text within this window
        self._DEDUP_RATIO  = 0.75  # Jaccard similarity above this → duplicate
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
        except WebSocketDisconnect:
            logger.info("WS client disconnected before auth")
            return
        except Exception as e:
            logger.warning("WS auth receive error: %s", e)
            return
        if first.get("type") != "auth":
            await _safe_send(ws,{"type": "error", "code": "AUTH_REQUIRED", "message": "First frame must be auth"})
            await ws.close(code=4001)
            return
        try:
            decode_token(first["token"])
        except Exception as auth_err:
            import traceback
            logger.warning("WS auth failed: %s\n%s", auth_err, traceback.format_exc())
            await _safe_send(ws,{"type": "error", "code": "AUTH_FAILED", "message": "Invalid token"})
            await ws.close(code=4001)
            return

        logger.info("WS auth OK — waiting for session_start")
        try:
            while True:
                msg = await ws.receive()
                if "bytes" in msg:
                    await self._handle_audio(ws, msg["bytes"], ctx_mgr, rag, session_ctx)
                elif "text" in msg:
                    data = json.loads(msg["text"])
                    mtype = data.get("type")
                    if mtype == "session_start":
                        logger.info("session_start received: %s", data.get("session_id"))
                        ctx_mgr, rag, session_ctx = await self._start_session(ws, data)
                    elif mtype == "session_pause":
                        if ctx_mgr:
                            await ctx_mgr.set_state("paused")
                        await _safe_send(ws,{"type": "status", "state": "paused", "latency_ms": 0})
                    elif mtype == "session_end":
                        break
                    elif mtype == "manual_ask":
                        await self._handle_manual_ask(ws, data, session_ctx, rag, ctx_mgr)
        except WebSocketDisconnect as e:
            logger.info("Client disconnected (code=%s)", getattr(e, 'code', '?'))
        except RuntimeError as e:
            # Starlette raises RuntimeError (not WebSocketDisconnect) when receive()
            # is called after the disconnect message has already been consumed.
            if "disconnect" in str(e).lower():
                logger.info("WS already disconnected — exiting loop cleanly")
            else:
                logger.exception("Overlay WS runtime error: %s", e)
        except Exception as e:
            logger.exception("Overlay WS error: %s", e)
        finally:
            logger.info("WS session ending")
            # Stop background summariser
            stop_ev = session_ctx.get("_stop_summarizer")
            if stop_ev:
                stop_ev.set()
            # Cancel any pending utterance flush timers
            flush_tasks = session_ctx.get("_flush_tasks", {})
            for task in flush_tasks.values():
                if task and not task.done():
                    task.cancel()
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.close()
            except Exception:
                pass

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

        # --- Utterance buffer: accumulate chunks into paragraphs ---
        # Like a messaging app — text accumulates until the speaker pauses,
        # then the whole utterance is emitted as one bubble.
        # State is per-session-local (not on self) so sessions don't bleed.
        SILENCE_FLUSH_S = 2.5   # seconds of silence before flushing utterance
        utterance: dict[str, list[str]] = {"user": [], "interviewer": []}
        flush_tasks: dict[str, asyncio.Task | None] = {"user": None, "interviewer": None}
        # seq counter for emitted bubbles (independent of chunk seq)
        bubble_seq = [0]

        async def _flush_utterance(speaker: str):
            """Wait for silence timeout, then emit the accumulated paragraph."""
            await asyncio.sleep(SILENCE_FLUSH_S)
            parts = utterance[speaker]
            if not parts:
                return
            text = " ".join(parts)
            utterance[speaker] = []
            bubble_seq[0] += 1
            seq = bubble_seq[0]
            entry = TranscriptEntry(speaker=speaker, text=text, seq=seq)
            await ctx_mgr.push_transcript(entry)
            await _safe_send(ws, {"type": "transcript", "speaker": speaker, "text": text, "seq": seq})
            logger.info("[pipeline] bubble | speaker=%s | text=%r", speaker, text[:80])

        def _schedule_flush(speaker: str):
            """Reset the silence timer for this speaker."""
            old = flush_tasks[speaker]
            if old and not old.done():
                old.cancel()
            flush_tasks[speaker] = asyncio.create_task(_flush_utterance(speaker))

        ctx["_utterance"] = utterance
        ctx["_schedule_flush"] = _schedule_flush
        ctx["_flush_tasks"] = flush_tasks

        # --- Background summariser ---
        stop_summarizer = asyncio.Event()
        ctx["_stop_summarizer"] = stop_summarizer
        asyncio.create_task(run_summarizer(ctx_mgr, stop_summarizer))

        await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
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

            t_transcribe = time.monotonic()
            result = await self._audio.transcribe(pcm, speaker=speaker)
            transcribe_ms = round((time.monotonic() - t_transcribe) * 1000)

            if not result["text"]:
                return

            # --- Dedup: suppress near-identical chunks within the window ---
            text = result["text"]
            sid  = session_ctx.get("_session_id", "unknown")
            now  = time.time()
            recent = self._recent_texts.setdefault(sid, [])
            recent[:] = [(t, tx) for t, tx in recent if now - t < self._DEDUP_WINDOW]

            def _jaccard(a: str, b: str) -> float:
                sa, sb = set(a.lower().split()), set(b.lower().split())
                if not sa and not sb: return 1.0
                return len(sa & sb) / len(sa | sb)

            if any(_jaccard(text, tx) >= self._DEDUP_RATIO for _, tx in recent):
                logger.debug("[pipeline] dedup suppressed: %r", text[:60])
                return
            recent.append((now, text))

            logger.info("[pipeline] chunk | transcribe=%dms | speaker=%s | text=%r",
                        transcribe_ms, speaker, text[:60])

            # --- AI trigger: run BERT immediately on every interviewer chunk ---
            # Don't wait for silence buffer — start AI response as soon as a
            # question is detected so the response arrives while they finish talking.
            if speaker == "interviewer":
                await self._maybe_trigger_suggestion(ws, ctx_mgr, rag, session_ctx, text)

            # --- Utterance buffer: accumulate into paragraph, flush on silence ---
            # Display only — paragraph bubble emitted after 2.5s silence.
            utterance: dict = session_ctx.get("_utterance", {})
            schedule_flush = session_ctx.get("_schedule_flush")
            if utterance is not None and schedule_flush is not None:
                utterance[speaker].append(text)
                schedule_flush(speaker)   # resets the 2.5s silence timer
            else:
                # Fallback: no buffer state (shouldn't happen) — emit immediately
                entry = TranscriptEntry(speaker=speaker, text=text, seq=seq)
                await ctx_mgr.push_transcript(entry)
                await _safe_send(ws, {"type": "transcript", "speaker": speaker, "text": text, "seq": seq})

        except WebSocketDisconnect:
            raise
        except RuntimeError as e:
            if "disconnect" in str(e).lower():
                raise WebSocketDisconnect()
            logger.exception("Audio frame processing error (runtime): %s", e)
        except Exception:
            logger.exception("Audio frame processing error")
            await _safe_send(ws, {"type": "error", "code": "AUDIO_ERROR", "message": "Audio processing failed"})

    async def _maybe_trigger_suggestion(self, ws: WebSocket, ctx_mgr, rag, session_ctx: dict, text: str):
        """Run BERT on a completed interviewer utterance and stream a suggestion if it's a question."""
        now = time.monotonic()
        if not self._use_bert or self._bert is None:
            return
        if now - self._last_trigger <= BERT_COOLDOWN:
            return
        t_bert = time.monotonic()
        is_q = await self._bert.is_question(text)
        bert_ms = round((time.monotonic() - t_bert) * 1000)
        logger.info("[pipeline] bert=%dms | is_question=%s", bert_ms, is_q)
        if is_q:
            self._last_trigger = now
            await self._stream_suggestion(ws, ctx_mgr, rag, session_ctx, question_text=text)

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
                    await _safe_send(ws,{"type": "suggestion_delta", "delta": cached_response})
                    await _safe_send(ws,{"type": "suggestion_end"})
                    return

        await _safe_send(ws,{"type": "status", "state": "thinking", "latency_ms": 0})

        # --- Parallel fetch: transcript window + RAG + summary + facts ---
        t_fetch = time.monotonic()
        rag_coro = rag.retrieve(question_text, k=3) if (rag and question_text) else _empty_list()
        transcript, rag_chunks, summary, facts = await asyncio.gather(
            ctx_mgr.get_window(n=15),
            rag_coro,
            ctx_mgr.get_summary(),
            ctx_mgr.get_facts(),
        )
        fetch_ms = round((time.monotonic() - t_fetch) * 1000)
        logger.info("[pipeline] context_fetch=%dms | rag_chunks=%d | has_summary=%s",
                    fetch_ms, len(rag_chunks), bool(summary))

        t0 = time.monotonic()
        full_response: list[str] = []
        try:
            first = True
            batch: list[str] = []

            async for delta in self._llm.stream_suggestion(
                transcript=transcript,
                context=session_ctx,
                rag_chunks=rag_chunks,
                summary=summary,
                facts=facts,
            ):
                if first:
                    latency = round((time.monotonic() - t0) * 1000)
                    logger.info("[pipeline] llm_first_token=%dms", latency)
                    await _safe_send(ws,{"type": "status", "state": "listening", "latency_ms": latency})
                    first = False
                batch.append(delta)
                full_response.append(delta)
                # Flush when buffer reaches WS_BATCH_CHARS — reduces frame count
                # by 70–80% vs. sending one token at a time.
                if sum(len(d) for d in batch) >= WS_BATCH_CHARS:
                    await _safe_send(ws,{"type": "suggestion_delta", "delta": "".join(batch)})
                    batch = []

            if batch:
                await _safe_send(ws,{"type": "suggestion_delta", "delta": "".join(batch)})
            await _safe_send(ws,{"type": "suggestion_end"})

            total_llm_ms = round((time.monotonic() - t0) * 1000)
            logger.info(
                "[pipeline] llm_total=%dms | tokens=%d chars",
                total_llm_ms, sum(len(d) for d in full_response),
            )

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
                await _safe_send(ws,{"type": "suggestion_delta", "delta": cached_response})
                await _safe_send(ws,{"type": "suggestion_end"})
            else:
                await _safe_send(ws,{"type": "error", "code": "LLM_RATE_LIMITED", "message": "Rate limited"})
                await _safe_send(ws,{"type": "status", "state": "listening", "latency_ms": 0})
        except Exception:
            logger.exception("Suggestion streaming error")
            await _safe_send(ws,{"type": "error", "code": "LLM_ERROR", "message": "Suggestion failed"})
            await _safe_send(ws,{"type": "status", "state": "listening", "latency_ms": 0})

    async def _handle_manual_ask(self, ws: WebSocket, data: dict, session_ctx: dict, rag, ctx_mgr=None):
        text = data.get("text", "")
        if not text:
            await _safe_send(ws,{"type": "error", "code": "INVALID_REQUEST", "message": "text is required"})
            return

        # --- Per-session rate limiting ---
        session_id = session_ctx.get("_session_id", "unknown")
        now = time.time()
        count, window_start = self._ask_rate.get(session_id, (0, now))
        if now - window_start >= ASK_RATE_WINDOW:
            count, window_start = 0, now
        if count >= ASK_RATE_LIMIT:
            await _safe_send(ws,{
                "type": "error",
                "code": "ASK_RATE_LIMITED",
                "message": f"Maximum {ASK_RATE_LIMIT} asks per minute reached. Please wait.",
            })
            return
        self._ask_rate[session_id] = (count + 1, window_start)

        mode = data.get("mode", "hints")
        rag_chunks = await rag.retrieve(text, k=3) if rag else []
        if ctx_mgr:
            summary, facts = await asyncio.gather(ctx_mgr.get_summary(), ctx_mgr.get_facts())
        else:
            summary, facts = "", ""

        await _safe_send(ws, {"type": "status", "state": "thinking", "latency_ms": 0})
        t0 = time.monotonic()

        try:
            if mode == "solve":
                # Collect the full solution for Judge0 while streaming to the user.
                solution_parts: list[str] = []
                batch: list[str] = []
                first = True
                async for delta in self._llm.stream_manual_ask(text, mode=mode, context=session_ctx, rag_chunks=rag_chunks, summary=summary, facts=facts):
                    if first:
                        latency = round((time.monotonic() - t0) * 1000)
                        await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": latency})
                        first = False
                    solution_parts.append(delta)
                    batch.append(delta)
                    if sum(len(d) for d in batch) >= WS_BATCH_CHARS:
                        await _safe_send(ws,{"type": "suggestion_delta", "delta": "".join(batch)})
                        batch = []
                if batch:
                    await _safe_send(ws,{"type": "suggestion_delta", "delta": "".join(batch)})
                await _safe_send(ws,{"type": "suggestion_end"})

                # Execute with Judge0 after solution is assembled
                solution = "".join(solution_parts)
                lang = data.get("language", "python")
                code_result = await self._runner.execute(solution, language=lang)
                await _safe_send(ws,{
                    "type": "code_result",
                    "language": lang,
                    "output": code_result["output"],
                    "solution": solution,
                })
            else:
                # hints / ultra — stream token-by-token
                batch: list[str] = []
                first = True
                async for delta in self._llm.stream_manual_ask(text, mode=mode, context=session_ctx, rag_chunks=rag_chunks, summary=summary, facts=facts):
                    if first:
                        latency = round((time.monotonic() - t0) * 1000)
                        await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": latency})
                        first = False
                    batch.append(delta)
                    if sum(len(d) for d in batch) >= WS_BATCH_CHARS:
                        await _safe_send(ws,{"type": "suggestion_delta", "delta": "".join(batch)})
                        batch = []
                if batch:
                    await _safe_send(ws,{"type": "suggestion_delta", "delta": "".join(batch)})
                await _safe_send(ws,{"type": "suggestion_end"})

        except CodeRunnerError as e:
            await _safe_send(ws, {"type": "error", "code": e.code, "message": e.message})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
        except LLMRateLimitedError:
            await _safe_send(ws, {"type": "error", "code": "LLM_RATE_LIMITED", "message": "Rate limited"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
        except Exception:
            logger.exception("Manual ask streaming error")
            await _safe_send(ws, {"type": "error", "code": "LLM_ERROR", "message": "Request failed"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
