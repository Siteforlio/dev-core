import asyncio, logging, json, time, hashlib
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState
from app.core.security import decode_token
from app.core.exceptions import BertClassifierError, LLMRateLimitedError
from app.services.cluely.audio_service import AudioService, parse_audio_frame
from app.services.cluely.vision_service import VisionService
from app.services.cluely.context_manager import ContextManager
from app.services.cluely.bert_classifier import BertClassifier
from app.services.cluely.speaker_diarizer import SpeakerDiarizer
from app.services.cluely.assessment_agent import AssessmentAgent
from app.services.cluely.rag_service import RagService
from app.services.cluely.llm_service import LLMService
from app.services.cluely.outcome_service import OutcomeService
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
        self._vision  = VisionService()
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

        # One diarizer per service instance; reset() called per session.
        self._diarizer = SpeakerDiarizer()

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
                        # Send initial title to frontend immediately
                        title = session_ctx.get("_initial_title", "")
                        if title:
                            await _safe_send(ws, {"type": "session_title", "title": title})
                    elif mtype == "session_pause":
                        if ctx_mgr:
                            await ctx_mgr.set_state("paused")
                        await _safe_send(ws, {"type": "status", "state": "paused", "latency_ms": 0})
                    elif mtype == "session_end":
                        break
                    elif mtype == "manual_ask":
                        await self._handle_manual_ask(ws, data, session_ctx, rag, ctx_mgr, repo)
                    elif mtype == "assessment_trigger":
                        # Route to the assessment agent if one is active for this session
                        agent: AssessmentAgent | None = session_ctx.get("_assessment_agent")
                        if agent:
                            asyncio.create_task(agent.handle_assessment_trigger(data))
                    elif mtype == "screenshot_frame":
                        await self._handle_screenshot(ws, data, session_ctx)
                    elif mtype == "screenshot_clear":
                        sid = session_ctx.get("_session_id", "")
                        self._vision.clear_buffer(sid)
                        await _safe_send(ws, {"type": "screenshot_cleared"})
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
            # Close assessment agent resources (browser etc.)
            agent = session_ctx.get("_assessment_agent")
            if agent:
                try:
                    await agent.close()
                except Exception:
                    pass
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
                        # Generate AI title + summary from transcript before closing
                        transcript_buf = session_ctx.get("_transcript_buf", [])
                        post_summary = None
                        ai_title = None
                        if transcript_buf:
                            full_text = "\n".join(
                                f"{e.speaker}: {e.text}" for e in transcript_buf
                            )
                            try:
                                from app.services.cluely.deepseek_client import deepseek_generate
                                ai_title = await deepseek_generate(
                                    f"Give this interview session a short title (5-7 words max) based on the transcript below. Reply with ONLY the title, no quotes.\n\n{full_text[:1200]}",
                                    system="You are a concise title generator.",
                                    temperature=0.3, max_tokens=20,
                                )
                                ai_title = ai_title.strip().strip('"').strip("'")
                                post_summary = await deepseek_generate(
                                    f"Summarize this interview session in 2-3 sentences. Focus on topics covered and how the candidate performed.\n\n{full_text[:3000]}",
                                    system="You are a concise interview session summarizer.",
                                    temperature=0.3, max_tokens=150,
                                )
                            except Exception as e:
                                logger.warning("[repo] AI title/summary failed: %s", e)

                        await repo.end_session(sid, post_summary=post_summary)

                        if ai_title:
                            try:
                                from sqlalchemy import text as sa_text
                                # Only overwrite date-based fallback titles, not context-derived ones
                                initial = session_ctx.get("_initial_title", "")
                                needs_ai_title = not initial or initial.startswith("Session ")
                                if needs_ai_title:
                                    await repo._db.execute(
                                        sa_text("UPDATE cluely_sessions SET title = :title WHERE id = :id"),
                                        {"title": ai_title, "id": sid},
                                    )
                                    await repo._db.commit()
                                    logger.info("[repo] AI title saved: %r", ai_title)
                            except Exception as e:
                                logger.warning("[repo] title update failed: %s", e)
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

        self._diarizer.reset()

        ctx_mgr = ContextManager(redis=r, session_id=sid)
        if not await ctx_mgr.session_exists():
            await ctx_mgr.set_state("listening")

        # Session repository — write-through to PostgreSQL
        db = AsyncSessionLocal()
        from app.services.cluely.session_repository import SessionRepository
        repo = SessionRepository(db=db)
        repo.start_flush_loop()

        # Derive initial title from context if available
        company  = ctx.get("company", "")
        role     = ctx.get("job_title", "")
        from datetime import datetime
        date_str = datetime.now().strftime("%b %d")
        if role and company:
            initial_title = f"{role} at {company}"
        elif role:
            initial_title = f"{role} Interview"
        elif company:
            initial_title = f"{company} Interview"
        else:
            initial_title = f"Session {date_str}"

        ctx["_initial_title"] = initial_title

        session_type: str | None = ctx.get("assessmentMode") or ctx.get("assessment_mode") or None
        try:
            await repo.create_session(
                session_id=sid,
                user_id=user_id,
                company=company,
                role=role,
                title=initial_title,
                application_id=ctx.get("application_id"),
                session_type=session_type,
            )
        except Exception as e:
            logger.error("[repo] create_session failed: %s", e)

        # RAG index (background)
        # - If a project_root is set (live coding mode): index the whole codebase with Semble
        # - Otherwise fall back to indexing any attached files (documents, resumes, etc.)
        rag = RagService()
        project_root = ctx.get("projectRoot") or ctx.get("project_root")
        files = ctx.get("files", [])
        index_targets = [project_root] if project_root else files
        if index_targets:
            task = asyncio.create_task(rag.build_index(index_targets))
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
            # Keep rolling buffer in ctx for manual_ask intent detection
            buf = ctx.setdefault("_transcript_buf", [])
            buf.append(entry)
            if len(buf) > 30:
                ctx["_transcript_buf"] = buf[-30:]
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

        # Assessment agent — created for non-present assessment modes
        # "present" mode gets tool access but no autonomous agent loop
        assessment_mode: str | None = ctx.get("assessmentMode") or ctx.get("assessment_mode")
        if assessment_mode and assessment_mode != "present":
            sid_for_tools = ctx.get("session_id", "")

            async def _ws_send(event: dict) -> None:
                await _safe_send(ws, event)
                # Record which tools are used in the session
                if event.get("type") == "tool:event" and event.get("status") == "start":
                    tool = event.get("tool", "")
                    if tool and repo:
                        try:
                            await repo.record_tool_used(sid_for_tools, tool)
                        except Exception:
                            pass

            agent = AssessmentAgent(
                mode=assessment_mode,
                session_ctx=ctx,
                send=_ws_send,
                project_root=ctx.get("projectRoot") or ctx.get("project_root"),
                file_paths=ctx.get("file_paths", []),
            )
            ctx["_assessment_agent"] = agent
            logger.info("[assessment] Agent created | mode=%s", assessment_mode)
            # Auto-trigger on start so agent immediately begins reading the screen
            asyncio.create_task(agent.handle_assessment_trigger({"action": "start"}))

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
            if stream == "mic":
                speaker = "user"
                # Feed mic frames into the diarizer to build the user's voice profile.
                self._diarizer.enroll_user(pcm)
            else:
                # System audio: use voice embeddings to detect echo/bleed vs interviewer.
                speaker = self._diarizer.classify_system_audio(pcm)

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
                cached_response = cached.decode() if isinstance(cached, (bytes, bytearray)) else str(cached)
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
                    await _safe_send(ws, {"type": "suggestion_delta", "delta": cached.decode() if isinstance(cached, (bytes, bytearray)) else str(cached)})
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
    # Manual ask — tool-augmented via ChatAgent
    # ------------------------------------------------------------------
    # Screenshot handler
    # ------------------------------------------------------------------

    async def _handle_screenshot(self, ws: WebSocket, data: dict, session_ctx: dict) -> None:
        sid = session_ctx.get("_session_id", "anon")
        image_b64 = data.get("image_b64", "")

        if not image_b64:
            await _safe_send(ws, {"type": "error", "code": "INVALID_REQUEST", "message": "image_b64 required"})
            return

        # Add to buffer
        buf_size = self._vision.add_screenshot(sid, image_b64)

        # Tell the overlay how many screenshots are buffered
        await _safe_send(ws, {"type": "screenshot_buffered", "count": buf_size})

        # Analyze immediately — all buffered images together
        mode = session_ctx.get("assessmentMode") or session_ctx.get("_assessment_mode")
        extra_context = None
        ctx_parts = []
        if session_ctx.get("job_title"):
            ctx_parts.append(f"Role: {session_ctx['job_title']}")
        if session_ctx.get("company"):
            ctx_parts.append(f"Company: {session_ctx['company']}")
        if ctx_parts:
            extra_context = ", ".join(ctx_parts)

        await _safe_send(ws, {"type": "status", "state": "thinking", "latency_ms": 0})

        result = await self._vision.analyze(sid, mode=mode, extra_context=extra_context)

        if result["text"]:
            # Stream the response token by token via suggestion events
            words = result["text"].split(" ")
            for i, word in enumerate(words):
                delta = word if i == 0 else " " + word
                await _safe_send(ws, {"type": "suggestion_delta", "delta": delta, "done": False})
            await _safe_send(ws, {"type": "suggestion_end", "done": True})

        await _safe_send(ws, {
            "type": "screenshot_result",
            "needs_more": result["needs_more"],
            "buffer_size": result["buffer_size"],
            "cleared": result["cleared"],
        })
        await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})

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

        rag_chunks = await rag.retrieve(text, k=3) if rag else []
        if ctx_mgr:
            summary, facts = await asyncio.gather(ctx_mgr.get_summary(), ctx_mgr.get_facts())
        else:
            summary, facts = "", ""
        recent = session_ctx.get("_transcript_buf", [])[-15:]
        chat_history: list[dict] = data.get("history", [])

        await _safe_send(ws, {"type": "status", "state": "thinking", "latency_ms": 0})
        t0 = time.monotonic()
        full_response: list[str] = []

        # Build a tool-aware send that also records tool usage to DB
        sid_for_tools = session_id
        async def _chat_send(event: dict) -> None:
            await _safe_send(ws, event)
            if event.get("type") == "tool:event" and event.get("status") == "start":
                tool = event.get("tool", "")
                if tool and repo:
                    try:
                        await repo.record_tool_used(sid_for_tools, tool)
                    except Exception:
                        pass

        # Build FileService if a project root was given at session start
        from app.services.cluely.file_service import FileService
        from app.services.cluely.chat_agent import ChatAgent

        file_svc: FileService | None = None
        project_root = session_ctx.get("projectRoot") or session_ctx.get("project_root")
        if project_root:
            try:
                file_svc = FileService(project_root)
            except ValueError:
                pass

        agent = ChatAgent(session_ctx=session_ctx, send=_chat_send, file_service=file_svc)

        try:
            first = True
            batch: list[str] = []
            async for delta in agent.handle(text, rag_chunks, summary, facts, recent, chat_history):
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
            mode = data.get("mode", "hints")
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

        except LLMRateLimitedError:
            await _safe_send(ws, {"type": "error", "code": "LLM_RATE_LIMITED", "message": "Rate limited"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
        except Exception:
            logger.exception("Manual ask error")
            await _safe_send(ws, {"type": "error", "code": "LLM_ERROR", "message": "Request failed"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
