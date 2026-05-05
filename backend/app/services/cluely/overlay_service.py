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
from app.services.cluely.outcome_service import OutcomeService
from app.services.cluely.code_runner import CodeRunner
from app.services.cluely.summarizer import run_summarizer
from app.schemas.cluely import TranscriptEntry

logger = logging.getLogger(__name__)

BERT_COOLDOWN       = 0.5    # seconds between BERT triggers
SUGGESTION_CACHE_TTL = 300   # 5 minutes — skip LLM for identical questions
ASK_RATE_LIMIT      = 10     # max manual asks per window
ASK_RATE_WINDOW     = 60     # seconds
WS_BATCH_CHARS      = 12     # buffer chars before flushing to WebSocket


async def _empty_list() -> list:
    return []


async def _safe_send(ws: WebSocket, data: dict) -> bool:
    try:
        if ws.client_state != WebSocketState.CONNECTED:
            return False
        await ws.send_json(data)
        return True
    except (WebSocketDisconnect, RuntimeError, Exception):
        return False


class OverlayService:
    def __init__(self):
        self._audio   = AudioService()
        self._llm     = LLMService()
        self._runner  = CodeRunner()
        self._last_trigger = 0.0
        # ask_rate: {session_id: (count, window_start_timestamp)}
        self._ask_rate: dict[str, tuple[int, float]] = {}
        # recent transcripts for dedup: {session_id: [(timestamp, text), ...]}
        self._recent_texts: dict[str, list[tuple[float, str]]] = {}
        self._DEDUP_WINDOW = 4.0
        self._DEDUP_RATIO  = 0.75
        try:
            self._bert = BertClassifier()
            self._use_bert = True
        except BertClassifierError:
            logger.warning("BERT unavailable — using silence detection fallback")
            self._use_bert = False
            self._bert = None

    # ------------------------------------------------------------------
    # WebSocket entry point
    # ------------------------------------------------------------------

    async def handle(self, ws: WebSocket) -> None:
        await ws.accept()
        ctx_mgr: ContextManager | None = None
        rag: RagService | None = None
        session_ctx: dict = {}
        repo = None

        # Auth gate
        try:
            first = await asyncio.wait_for(ws.receive_json(), timeout=3.0)
        except asyncio.TimeoutError:
            await ws.close(code=4001)
            return
        except WebSocketDisconnect:
            return
        except Exception as e:
            logger.warning("WS auth receive error: %s", e)
            return

        if first.get("type") != "auth":
            await _safe_send(ws, {"type": "error", "code": "AUTH_REQUIRED", "message": "First frame must be auth"})
            await ws.close(code=4001)
            return

        try:
            user_id = decode_token(first["token"])
        except Exception as auth_err:
            import traceback
            logger.warning("WS auth failed: %s\n%s", auth_err, traceback.format_exc())
            await _safe_send(ws, {"type": "error", "code": "AUTH_FAILED", "message": "Invalid token"})
            await ws.close(code=4001)
            return

        logger.info("WS auth OK — waiting for session_start | user_id=%s", user_id)
        try:
            while True:
                msg = await ws.receive()
                if "bytes" in msg:
                    await self._handle_audio(ws, msg["bytes"], ctx_mgr, rag, session_ctx)
                elif "text" in msg:
                    data = json.loads(msg["text"])
                    mtype = data.get("type")
                    if mtype == "session_start":
                        logger.info("session_start | sid=%s", data.get("session_id"))
                        ctx_mgr, rag, session_ctx, repo = await self._start_session(
                            ws, data, user_id
                        )
                    elif mtype == "session_pause":
                        if ctx_mgr:
                            await ctx_mgr.set_state("paused")
                        await _safe_send(ws, {"type": "status", "state": "paused", "latency_ms": 0})
                    elif mtype == "session_end":
                        break
                    elif mtype == "manual_ask":
                        await self._handle_manual_ask(ws, data, session_ctx, rag, ctx_mgr, repo)
                    elif mtype == "outcome_pill_ask":
                        await self._handle_outcome_pill_ask(ws, data, session_ctx, rag, ctx_mgr, repo)
        except WebSocketDisconnect as e:
            logger.info("Client disconnected (code=%s)", getattr(e, "code", "?"))
        except RuntimeError as e:
            if "disconnect" in str(e).lower():
                logger.info("WS already disconnected — exiting cleanly")
            else:
                logger.exception("Overlay WS runtime error: %s", e)
        except Exception as e:
            logger.exception("Overlay WS error: %s", e)
        finally:
            logger.info("WS session ending")
            stop_ev = session_ctx.get("_stop_summarizer")
            if stop_ev:
                stop_ev.set()
            for task in session_ctx.get("_flush_tasks", {}).values():
                if task and not task.done():
                    task.cancel()
            if repo:
                repo.stop_flush_loop()
                sid = session_ctx.get("_session_id")
                if sid:
                    try:
                        await repo.end_session(sid)
                    except Exception as e:
                        logger.error("[repo] end_session failed: %s", e)
                try:
                    await repo._db.close()
                except Exception:
                    pass
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Session start
    # ------------------------------------------------------------------

    async def _start_session(self, ws: WebSocket, data: dict, user_id: str):
        from app.core.cache import get_redis
        from app.core.database import AsyncSessionLocal

        sid = data["session_id"]
        ctx = data.get("context", {})
        ctx["_session_id"] = sid

        r = await get_redis()

        # Outcome service — Redis-backed cache for outcome inference
        outcome_svc = OutcomeService(redis=r)
        ctx["_outcome_svc"] = outcome_svc

        ctx_mgr = ContextManager(redis=r, session_id=sid)
        if not await ctx_mgr.session_exists():
            await ctx_mgr.set_state("listening")

        # Session repository — write-through to PostgreSQL
        db = AsyncSessionLocal()
        from app.services.cluely.session_repository import SessionRepository
        repo = SessionRepository(db=db)
        repo.start_flush_loop()

        try:
            await repo.create_session(
                session_id=sid,
                user_id=user_id,
                company=ctx.get("company", ""),
                role=ctx.get("job_title", ""),
                application_id=ctx.get("application_id"),
            )
        except Exception as e:
            logger.error("[repo] create_session failed: %s", e)

        # RAG index (background)
        rag = RagService()
        files = ctx.get("files", [])
        if files:
            task = asyncio.create_task(rag.build_index(files))
            task.add_done_callback(
                lambda t: logger.error("RAG build failed: %s", t.exception()) if t.exception() else None
            )

        # Utterance buffer — accumulate chunks into paragraphs before emitting
        SILENCE_FLUSH_S = 2.5
        utterance: dict[str, list[str]] = {"user": [], "interviewer": []}
        flush_tasks: dict[str, asyncio.Task | None] = {"user": None, "interviewer": None}
        bubble_seq = [0]

        async def _flush_utterance(speaker: str):
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
            # Persist transcript line
            try:
                await repo.append_transcript_line(
                    session_id=sid, speaker=speaker, text_content=text, seq=seq
                )
            except Exception as e:
                logger.error("[repo] transcript line failed: %s", e)
            logger.info("[pipeline] bubble | speaker=%s | text=%r", speaker, text[:80])

        def _schedule_flush(speaker: str):
            old = flush_tasks[speaker]
            if old and not old.done():
                old.cancel()
            flush_tasks[speaker] = asyncio.create_task(_flush_utterance(speaker))

        ctx["_utterance"]      = utterance
        ctx["_schedule_flush"] = _schedule_flush
        ctx["_flush_tasks"]    = flush_tasks
        ctx["_repo"]           = repo

        # Background summariser
        stop_summarizer = asyncio.Event()
        ctx["_stop_summarizer"] = stop_summarizer
        asyncio.create_task(run_summarizer(ctx_mgr, stop_summarizer))

        await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
        return ctx_mgr, rag, ctx, repo

    # ------------------------------------------------------------------
    # Audio frame handler
    # ------------------------------------------------------------------

    async def _handle_audio(self, ws, raw, ctx_mgr, rag, session_ctx):
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

            text = result["text"]
            sid  = session_ctx.get("_session_id", "unknown")
            now  = time.time()
            recent = self._recent_texts.setdefault(sid, [])
            recent[:] = [(t, tx) for t, tx in recent if now - t < self._DEDUP_WINDOW]

            def _jaccard(a: str, b: str) -> float:
                sa, sb = set(a.lower().split()), set(b.lower().split())
                if not sa and not sb:
                    return 1.0
                return len(sa & sb) / len(sa | sb)

            if any(_jaccard(text, tx) >= self._DEDUP_RATIO for _, tx in recent):
                logger.debug("[pipeline] dedup suppressed: %r", text[:60])
                return
            recent.append((now, text))

            logger.info("[pipeline] chunk | transcribe=%dms | speaker=%s | text=%r",
                        transcribe_ms, speaker, text[:60])

            if speaker == "interviewer":
                # Question detected → infer outcome, set up gap monitoring
                await self._maybe_trigger_outcome(ws, ctx_mgr, rag, session_ctx, text)
            else:
                # User speaking → check gap against current inferred outcome
                await self._maybe_trigger_gap(ws, ctx_mgr, rag, session_ctx, text)

            # Utterance buffer
            utterance     = session_ctx.get("_utterance", {})
            schedule_flush = session_ctx.get("_schedule_flush")
            if utterance is not None and schedule_flush is not None:
                utterance[speaker].append(text)
                schedule_flush(speaker)
            else:
                entry = TranscriptEntry(speaker=speaker, text=text, seq=seq)
                await ctx_mgr.push_transcript(entry)
                await _safe_send(ws, {"type": "transcript", "speaker": speaker, "text": text, "seq": seq})

        except WebSocketDisconnect:
            raise
        except RuntimeError as e:
            if "disconnect" in str(e).lower():
                raise WebSocketDisconnect()
            logger.exception("Audio frame error (runtime): %s", e)
        except Exception:
            logger.exception("Audio frame error")
            await _safe_send(ws, {"type": "error", "code": "AUDIO_ERROR", "message": "Audio processing failed"})

    # ------------------------------------------------------------------
    # Outcome inference (Mode 1 + Mode 3 pill data)
    # ------------------------------------------------------------------

    async def _maybe_trigger_outcome(
        self, ws, ctx_mgr, rag, session_ctx: dict, question_text: str
    ):
        now = time.monotonic()
        if not self._use_bert or self._bert is None:
            return
        if now - self._last_trigger <= BERT_COOLDOWN:
            return

        t_bert = time.monotonic()
        is_q = await self._bert.is_question(question_text)
        bert_ms = round((time.monotonic() - t_bert) * 1000)
        logger.info("[pipeline] bert=%dms | is_question=%s", bert_ms, is_q)

        if not is_q:
            return

        self._last_trigger = now
        sid = session_ctx.get("_session_id", "unknown")

        # Infer outcome asynchronously — don't block audio pipeline
        outcome_svc: OutcomeService = session_ctx.get("_outcome_svc")
        if outcome_svc:
            try:
                outcome = await outcome_svc.infer_outcome(sid, question_text, session_ctx)
                # Stash for gap detection on subsequent user chunks
                session_ctx["_current_outcome"] = outcome
                session_ctx["_current_question"] = question_text
                session_ctx["_user_response_acc"] = []  # reset accumulator
                # Send outcome pill to UI (Mode 3)
                await _safe_send(ws, {
                    "type": "outcome_inferred",
                    "outcome": outcome,
                    "question": question_text,
                })
                logger.info("[outcome] pill sent | outcome=%r", outcome)
            except Exception as e:
                logger.warning("[outcome] infer failed: %s", e)

    # ------------------------------------------------------------------
    # Gap detection (Mode 2)
    # ------------------------------------------------------------------

    async def _maybe_trigger_gap(self, ws, ctx_mgr, rag, session_ctx: dict, user_text: str):
        outcome = session_ctx.get("_current_outcome")
        if not outcome:
            return

        # Accumulate user response chunks
        acc: list[str] = session_ctx.setdefault("_user_response_acc", [])
        acc.append(user_text)
        accumulated = " ".join(acc)

        # Only check after the user has said at least 20 words — avoids false positives
        if len(accumulated.split()) < 20:
            return

        outcome_svc: OutcomeService = session_ctx.get("_outcome_svc")
        if not outcome_svc:
            return

        gap = await outcome_svc.detect_gap(outcome, accumulated)
        if not gap:
            return

        # Gap detected — fire a correction suggestion and reset accumulator
        session_ctx["_user_response_acc"] = []
        logger.info("[outcome] gap detected — streaming correction")
        await self._stream_suggestion(
            ws, ctx_mgr, rag, session_ctx,
            question_text=session_ctx.get("_current_question", ""),
            trigger_type="auto_gap",
        )

    # ------------------------------------------------------------------
    # Suggestion streaming (shared by auto_gap + outcome_pill)
    # ------------------------------------------------------------------

    async def _stream_suggestion(
        self,
        ws,
        ctx_mgr: ContextManager,
        rag,
        session_ctx: dict,
        question_text: str = "",
        trigger_type: str = "auto_gap",
    ):
        from app.core.cache import get_redis

        session_id = session_ctx.get("_session_id", "unknown")
        q_hash = hashlib.md5(question_text.encode()).hexdigest() if question_text else ""

        # --- Suggestion cache in Redis (shared across restarts) ---
        r = await get_redis()
        cache_key = f"cluely:sugg_cache:{session_id}:{q_hash}" if q_hash else ""

        if cache_key:
            cached = await r.get(cache_key)
            if cached:
                cached_response = cached.decode()
                logger.debug("Suggestion cache hit | q_hash=%s", q_hash)
                await _safe_send(ws, {"type": "suggestion_delta", "delta": cached_response})
                await _safe_send(ws, {"type": "suggestion_end"})
                return

        await _safe_send(ws, {"type": "status", "state": "thinking", "latency_ms": 0})

        t_fetch = time.monotonic()
        rag_coro = rag.retrieve(question_text, k=3) if (rag and question_text) else _empty_list()
        transcript, rag_chunks, summary, facts = await asyncio.gather(
            ctx_mgr.get_window(n=15),
            rag_coro,
            ctx_mgr.get_summary(),
            ctx_mgr.get_facts(),
        )
        fetch_ms = round((time.monotonic() - t_fetch) * 1000)
        logger.info("[pipeline] context_fetch=%dms | rag=%d | summary=%s",
                    fetch_ms, len(rag_chunks), bool(summary))

        inferred_outcome = session_ctx.get("_current_outcome", "")
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
                inferred_outcome=inferred_outcome,
            ):
                if first:
                    latency = round((time.monotonic() - t0) * 1000)
                    await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": latency})
                    first = False
                batch.append(delta)
                full_response.append(delta)
                if sum(len(d) for d in batch) >= WS_BATCH_CHARS:
                    await _safe_send(ws, {"type": "suggestion_delta", "delta": "".join(batch)})
                    batch = []

            if batch:
                await _safe_send(ws, {"type": "suggestion_delta", "delta": "".join(batch)})
            await _safe_send(ws, {"type": "suggestion_end"})

            total_ms = round((time.monotonic() - t0) * 1000)
            logger.info("[pipeline] llm_total=%dms | chars=%d", total_ms, sum(len(d) for d in full_response))

            full_text = "".join(full_response)

            # Cache in Redis
            if cache_key and full_text:
                await r.setex(cache_key, SUGGESTION_CACHE_TTL, full_text)

            # Persist interaction
            repo = session_ctx.get("_repo")
            if repo and full_text:
                try:
                    await repo.append_interaction(
                        session_id=session_id,
                        trigger_type=trigger_type,
                        ai_response=full_text,
                        question_text=question_text or None,
                        inferred_outcome=inferred_outcome or None,
                    )
                except Exception as e:
                    logger.error("[repo] interaction write failed: %s", e)

        except LLMRateLimitedError:
            if cache_key:
                cached = await r.get(cache_key)
                if cached:
                    await _safe_send(ws, {"type": "suggestion_delta", "delta": cached.decode()})
                    await _safe_send(ws, {"type": "suggestion_end"})
                    return
            await _safe_send(ws, {"type": "error", "code": "LLM_RATE_LIMITED", "message": "Rate limited"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
        except Exception:
            logger.exception("Suggestion streaming error")
            await _safe_send(ws, {"type": "error", "code": "LLM_ERROR", "message": "Suggestion failed"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})

    # ------------------------------------------------------------------
    # Outcome pill — full answer on demand (Mode 3 tap)
    # ------------------------------------------------------------------

    async def _handle_outcome_pill_ask(self, ws, data: dict, session_ctx: dict, rag, ctx_mgr, repo):
        outcome = data.get("outcome") or session_ctx.get("_current_outcome", "")
        if not outcome:
            await _safe_send(ws, {"type": "error", "code": "NO_OUTCOME", "message": "No outcome available"})
            return

        sid = session_ctx.get("_session_id", "unknown")
        await _safe_send(ws, {"type": "status", "state": "thinking", "latency_ms": 0})
        t0 = time.monotonic()

        rag_chunks = await rag.retrieve(outcome, k=2) if rag else []

        async def _empty_str() -> str:
            return ""

        summary, facts, recent = await asyncio.gather(
            ctx_mgr.get_summary() if ctx_mgr else _empty_str(),
            ctx_mgr.get_facts() if ctx_mgr else _empty_str(),
            ctx_mgr.get_window(n=10) if ctx_mgr else _empty_list(),
        )

        full_response: list[str] = []
        batch: list[str] = []
        first = True

        try:
            async for delta in self._llm.stream_outcome_answer(
                outcome=outcome,
                context=session_ctx,
                rag_chunks=rag_chunks,
                summary=summary,
                facts=facts,
                recent=recent,
            ):
                if first:
                    latency = round((time.monotonic() - t0) * 1000)
                    await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": latency})
                    first = False
                batch.append(delta)
                full_response.append(delta)
                if sum(len(d) for d in batch) >= WS_BATCH_CHARS:
                    await _safe_send(ws, {"type": "suggestion_delta", "delta": "".join(batch)})
                    batch = []

            if batch:
                await _safe_send(ws, {"type": "suggestion_delta", "delta": "".join(batch)})
            await _safe_send(ws, {"type": "suggestion_end"})

            full_text = "".join(full_response)
            if repo and full_text:
                try:
                    await repo.append_interaction(
                        session_id=sid,
                        trigger_type="outcome_pill",
                        ai_response=full_text,
                        inferred_outcome=outcome,
                    )
                except Exception as e:
                    logger.error("[repo] pill interaction write failed: %s", e)

        except LLMRateLimitedError:
            await _safe_send(ws, {"type": "error", "code": "LLM_RATE_LIMITED", "message": "Rate limited"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
        except Exception:
            logger.exception("Outcome pill streaming error")
            await _safe_send(ws, {"type": "error", "code": "LLM_ERROR", "message": "Request failed"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})

    # ------------------------------------------------------------------
    # Manual ask
    # ------------------------------------------------------------------

    async def _handle_manual_ask(self, ws, data: dict, session_ctx: dict, rag, ctx_mgr=None, repo=None):
        text = data.get("text", "")
        if not text:
            await _safe_send(ws, {"type": "error", "code": "INVALID_REQUEST", "message": "text is required"})
            return

        session_id = session_ctx.get("_session_id", "unknown")
        now = time.time()
        count, window_start = self._ask_rate.get(session_id, (0, now))
        if now - window_start >= ASK_RATE_WINDOW:
            count, window_start = 0, now
        if count >= ASK_RATE_LIMIT:
            await _safe_send(ws, {
                "type": "error",
                "code": "ASK_RATE_LIMITED",
                "message": f"Maximum {ASK_RATE_LIMIT} asks per minute reached.",
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
        full_response: list[str] = []

        try:
            if mode == "solve":
                solution_parts: list[str] = []
                batch: list[str] = []
                first = True
                async for delta in self._llm.stream_manual_ask(text, mode=mode, context=session_ctx, rag_chunks=rag_chunks, summary=summary, facts=facts):
                    if first:
                        latency = round((time.monotonic() - t0) * 1000)
                        await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": latency})
                        first = False
                    solution_parts.append(delta)
                    full_response.append(delta)
                    batch.append(delta)
                    if sum(len(d) for d in batch) >= WS_BATCH_CHARS:
                        await _safe_send(ws, {"type": "suggestion_delta", "delta": "".join(batch)})
                        batch = []
                if batch:
                    await _safe_send(ws, {"type": "suggestion_delta", "delta": "".join(batch)})
                await _safe_send(ws, {"type": "suggestion_end"})

                solution = "".join(solution_parts)
                lang = data.get("language", "python")
                code_result = await self._runner.execute(solution, language=lang)
                await _safe_send(ws, {
                    "type": "code_result",
                    "language": lang,
                    "output": code_result["output"],
                    "solution": solution,
                })
            else:
                batch: list[str] = []
                first = True
                async for delta in self._llm.stream_manual_ask(text, mode=mode, context=session_ctx, rag_chunks=rag_chunks, summary=summary, facts=facts):
                    if first:
                        latency = round((time.monotonic() - t0) * 1000)
                        await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": latency})
                        first = False
                    full_response.append(delta)
                    batch.append(delta)
                    if sum(len(d) for d in batch) >= WS_BATCH_CHARS:
                        await _safe_send(ws, {"type": "suggestion_delta", "delta": "".join(batch)})
                        batch = []
                if batch:
                    await _safe_send(ws, {"type": "suggestion_delta", "delta": "".join(batch)})
                await _safe_send(ws, {"type": "suggestion_end"})

            full_text = "".join(full_response)
            if repo and full_text:
                try:
                    await repo.append_interaction(
                        session_id=session_id,
                        trigger_type="manual_ask",
                        ai_response=full_text,
                        question_text=text,
                        mode=mode,
                    )
                except Exception as e:
                    logger.error("[repo] manual ask write failed: %s", e)

        except CodeRunnerError as e:
            await _safe_send(ws, {"type": "error", "code": e.code, "message": e.message})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
        except LLMRateLimitedError:
            await _safe_send(ws, {"type": "error", "code": "LLM_RATE_LIMITED", "message": "Rate limited"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
        except Exception:
            logger.exception("Manual ask error")
            await _safe_send(ws, {"type": "error", "code": "LLM_ERROR", "message": "Request failed"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
