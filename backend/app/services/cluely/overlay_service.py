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

BERT_COOLDOWN        = 0.5   # seconds between BERT triggers
SUGGESTION_CACHE_TTL = 300   # 5 minutes — skip LLM for identical questions
WS_BATCH_CHARS       = 1     # flush tokens to WebSocket immediately for lowest latency

# Per-message-type rate limits: (max_count, window_seconds)
_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "manual_ask":         (10, 60),   # 10 asks/min
    "screenshot_frame":   (30, 60),   # 30 screenshots/min
    "assessment_trigger": (20, 60),   # 20 triggers/min
    "outcome_pill_ask":   (10, 60),   # 10 pill taps/min
}

# Legacy alias kept for code that still references it
ASK_RATE_LIMIT = 10
ASK_RATE_WINDOW = 60


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
    """
    WebSocket orchestrator for the devcore overlay.

    Dependencies are injectable for testability — pass mocks in tests,
    omit in production to use the real implementations.
    """

    def __init__(
        self,
        audio_service: AudioService | None = None,
        llm_service: LLMService | None = None,
        vision_service: VisionService | None = None,
    ):
        self._audio   = audio_service  or AudioService()
        self._llm     = llm_service    or LLMService()
        self._vision  = vision_service or VisionService()
        self._last_trigger = 0.0
        # rate tracking: {(session_id, msg_type): (count, window_start)}
        self._ask_rate: dict[tuple[str, str], tuple[int, float]] = {}
        # recent transcripts for dedup: {session_id: [(timestamp, text), ...]}
        self._recent_texts: dict[str, list[tuple[float, str]]] = {}
        self._DEDUP_WINDOW = 4.0
        self._DEDUP_RATIO  = 0.75
        # BERT classifier and diarizer are lazy-initialized on first use to avoid
        # loading weights (~80-500 MB) at session startup.
        if hasattr(audio_service, '_bert_override'):
            # test injection path
            self._bert = audio_service._bert_override  # type: ignore
            self._use_bert = self._bert is not None
            self._bert_checked = True
        else:
            self._bert: 'BertClassifier | None' = None
            self._use_bert: bool = False
            self._bert_checked: bool = False  # False = not yet attempted

        # Diarizer: None until first audio frame
        self._diarizer: 'SpeakerDiarizer | None' = None

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

        # Guard: Deepgram is required for audio transcription.
        # Check DB (user Settings) first, fall back to .env.
        from app.core.database import AsyncSessionLocal
        from app.core.config import get_api_key
        async with AsyncSessionLocal() as _check_db:
            _deepgram_key = await get_api_key(user_id, "deepgram_api_key", _check_db)
        if not _deepgram_key:
            await _safe_send(ws, {
                "type": "error",
                "code": "DEEPGRAM_MISSING",
                "message": (
                    "Deepgram API key is not set. DevCore needs it to transcribe your audio. "
                    "Go to Settings → API Keys and add your Deepgram key. "
                    "A fully local transcription option is planned for a future release so you won't need any external API."
                ),
            })
            await ws.close(code=4003)
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
                    elif mtype == "session_resume":
                        if ctx_mgr:
                            await ctx_mgr.set_state("listening")
                        await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
                    elif mtype == "session_end":
                        break
                    elif mtype == "manual_ask":
                        await self._handle_manual_ask(ws, data, session_ctx, rag, ctx_mgr, repo)
                    elif mtype == "assessment_trigger":
                        sid_rt = session_ctx.get("_session_id", "unknown")
                        if not self._is_rate_limited(sid_rt, "assessment_trigger"):
                            agent: AssessmentAgent | None = session_ctx.get("_assessment_agent")
                            if agent:
                                asyncio.create_task(agent.handle_assessment_trigger(data))
                    elif mtype == "screenshot_frame":
                        sid_rt = session_ctx.get("_session_id", "unknown")
                        if not self._is_rate_limited(sid_rt, "screenshot_frame"):
                            await self._handle_screenshot(ws, data, session_ctx)
                        else:
                            await _safe_send(ws, {"type": "error", "code": "RATE_LIMITED", "message": "Too many screenshots"})
                    elif mtype == "screenshot_clear":
                        sid = session_ctx.get("_session_id", "")
                        self._vision.clear_buffer(sid)
                        await _safe_send(ws, {"type": "screenshot_cleared"})
                    elif mtype == "outcome_pill_ask":
                        sid_rt = session_ctx.get("_session_id", "unknown")
                        if not self._is_rate_limited(sid_rt, "outcome_pill_ask"):
                            await self._handle_outcome_pill_ask(ws, data, session_ctx, rag, ctx_mgr, repo)
                        else:
                            await _safe_send(ws, {"type": "error", "code": "RATE_LIMITED", "message": "Too many requests"})
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
                        # end_session first — guarantees the record is marked ended
                        # even if the AI title/summary generation below fails or times out
                        await repo.end_session(sid, post_summary=None)
                    except Exception as e:
                        logger.error("[repo] end_session failed: %s", e)

                    # Fire AI title + summary as a detached background task with a hard
                    # 15s timeout so a slow LLM never blocks connection teardown.
                    transcript_buf = session_ctx.get("_transcript_buf", [])
                    if transcript_buf:
                        async def _generate_title_summary(
                            session_id: str,
                            buf: list,
                            initial_title: str,
                        ) -> None:
                            try:
                                from app.services.cluely.deepseek_client import deepseek_generate
                                from sqlalchemy import text as sa_text
                                from app.core.database import AsyncSessionLocal

                                full_text = "\n".join(f"{e.speaker}: {e.text}" for e in buf)
                                ai_title, post_summary = None, None
                                try:
                                    ai_title = await asyncio.wait_for(
                                        deepseek_generate(
                                            f"Give this session a short title (5-7 words max). Reply with ONLY the title, no quotes.\n\n{full_text[:1200]}",
                                            system="You are a concise title generator.",
                                            temperature=0.3, max_tokens=20,
                                        ),
                                        timeout=10,
                                    )
                                    ai_title = ai_title.strip().strip('"').strip("'")
                                    post_summary = await asyncio.wait_for(
                                        deepseek_generate(
                                            f"Summarize this session in 2-3 sentences.\n\n{full_text[:3000]}",
                                            system="You are a concise session summarizer.",
                                            temperature=0.3, max_tokens=150,
                                        ),
                                        timeout=10,
                                    )
                                except asyncio.TimeoutError:
                                    logger.warning("[repo] AI title/summary timed out")
                                except Exception as e:
                                    logger.warning("[repo] AI title/summary failed: %s", e)

                                async with AsyncSessionLocal() as db:
                                    if post_summary:
                                        await db.execute(
                                            sa_text("UPDATE cluely_sessions SET summary = :s WHERE id = :id"),
                                            {"s": post_summary, "id": session_id},
                                        )
                                    needs_ai_title = not initial_title or initial_title.startswith("Session ")
                                    if ai_title and needs_ai_title:
                                        await db.execute(
                                            sa_text("UPDATE cluely_sessions SET title = :title WHERE id = :id"),
                                            {"title": ai_title, "id": session_id},
                                        )
                                        logger.info("[repo] AI title saved: %r", ai_title)
                                    await db.commit()
                            except Exception as e:
                                logger.error("[repo] background title/summary task failed: %s", e)

                        asyncio.create_task(
                            _generate_title_summary(
                                sid,
                                list(transcript_buf),
                                session_ctx.get("_initial_title", ""),
                            )
                        )

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
        from app.core.database import AsyncSessionLocal
        from app.schemas.cluely import SessionStartRequest
        from pydantic import ValidationError

        # Validate and sanitise the incoming payload
        try:
            req = SessionStartRequest(
                session_id=data.get("session_id", ""),
                context=data.get("context", {}),
            )
        except ValidationError as e:
            logger.warning("[session] Invalid session_start payload: %s", e)
            await _safe_send(ws, {"type": "error", "code": "INVALID_REQUEST", "message": str(e)})
            return None, None, {}, None

        sid = req.session_id
        ctx = req.context.model_dump()
        ctx["_session_id"] = sid

        # Outcome service — in-memory cache for outcome inference
        outcome_svc = OutcomeService()
        ctx["_outcome_svc"] = outcome_svc

        if self._diarizer is not None:
            self._diarizer.reset()

        ctx_mgr = ContextManager(session_id=sid)
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
            # Ownership check: if session already exists, ensure it belongs to this user
            existing_owner = await repo.get_session_owner(sid)
            if existing_owner is not None and existing_owner != user_id:
                logger.warning(
                    "[security] session_id %s belongs to user %s, rejecting user %s",
                    sid, existing_owner, user_id,
                )
                await _safe_send(ws, {"type": "error", "code": "FORBIDDEN", "message": "Session access denied"})
                await ws.close(code=4003)
                return None, None, {}, None

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

        # Read any attached context files and store content directly in ctx
        # so they are injected into every LLM system prompt (up to 3000 chars each,
        # max 3 files, concatenated under extra_context).
        files = ctx.get("files", [])
        if files:
            extra_parts: list[str] = []
            for fpath in files[:3]:
                try:
                    from pathlib import Path as _Path
                    p = _Path(fpath).expanduser().resolve()
                    if p.is_file() and p.stat().st_size < 2 * 1024 * 1024:  # skip >2MB
                        text = p.read_text(encoding="utf-8", errors="ignore")
                        extra_parts.append(f"--- {p.name} ---\n{text}")
                        logger.info("[session] Loaded context file: %s (%d chars)", p.name, len(text))
                except Exception as e:
                    logger.warning("[session] Could not read context file %s: %s", fpath, e)
            if extra_parts:
                ctx["extra_context"] = "\n\n".join(extra_parts)

        # RAG index (background)
        # - If a project_root is set (live coding mode): index the whole codebase with Semble
        # - Otherwise skip (document files are now read directly into extra_context above)
        rag = RagService()
        project_root = ctx.get("projectRoot") or ctx.get("project_root")
        if project_root:
            task = asyncio.create_task(rag.build_index([project_root]))
            task.add_done_callback(
                lambda t: logger.error("RAG build failed: %s", t.exception()) if t.exception() else None
            )

        # Utterance buffer — accumulate chunks into paragraphs before emitting
        SILENCE_FLUSH_S = 1.0
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

        # Stream a greeting so the user immediately sees what context is loaded.
        asyncio.create_task(self._send_session_greeting(ws, ctx))

        # Warm up the DeepSeek HTTP client in the background so the first
        # user ask doesn't pay the TLS handshake + connection setup cost.
        asyncio.create_task(self._warmup_llm_client())

        return ctx_mgr, rag, ctx, repo

    # ------------------------------------------------------------------
    # Session greeting — streamed on connect so the user sees context status
    # ------------------------------------------------------------------

    async def _send_session_greeting(self, ws: WebSocket, ctx: dict) -> None:
        job_title     = ctx.get("job_title", "")
        company       = ctx.get("company", "")
        resume_text   = ctx.get("resume_text", "")
        jd_text       = ctx.get("jd_text", "")
        extra_context = ctx.get("extra_context", "")
        mode          = ctx.get("assessmentMode") or ctx.get("assessment_mode") or ""

        has_context = bool(job_title or company or resume_text or jd_text or extra_context)

        if has_context:
            # Summarise what's loaded — let the AI phrase it naturally
            parts: list[str] = []
            if job_title and company:
                parts.append(f"role: **{job_title}** at **{company}**")
            elif job_title:
                parts.append(f"role: **{job_title}**")
            elif company:
                parts.append(f"company: **{company}**")
            if resume_text:
                parts.append("resume loaded")
            if jd_text:
                parts.append("job description loaded")
            if extra_context:
                parts.append("context files loaded")
            if mode:
                parts.append(f"mode: **{mode}**")

            greeting = f"Session ready — {', '.join(parts)}. Listening now."
        else:
            greeting = "Session started — no context loaded. Ready to assist with anything you need."

        # Stream word-by-word so it appears as natural typing
        words = greeting.split(" ")
        for i, word in enumerate(words):
            delta = word if i == 0 else " " + word
            await _safe_send(ws, {"type": "suggestion_delta", "delta": delta})
            await asyncio.sleep(0.02)  # 20ms per word — fast but readable
        await _safe_send(ws, {"type": "suggestion_end"})

    async def _warmup_llm_client(self) -> None:
        """Fire a tiny request to establish TCP+TLS with DeepSeek so
        the first real ask doesn't pay the cold-start cost (~1-2s)."""
        try:
            from app.services.cluely.deepseek_client import deepseek_generate
            await asyncio.wait_for(
                deepseek_generate("hi", system="Reply with one word.", max_tokens=1),
                timeout=5,
            )
            logger.info("[warmup] DeepSeek client warmed up")
        except Exception as e:
            logger.debug("[warmup] DeepSeek warmup failed (non-fatal): %s", e)

    # ------------------------------------------------------------------
    # Audio frame handler
    # ------------------------------------------------------------------

    async def _handle_audio(self, ws, raw, ctx_mgr, rag, session_ctx):
        logger.debug("[audio-raw] binary frame received: %d bytes | ctx_mgr=%s", len(raw), ctx_mgr is not None)
        if ctx_mgr is None:
            logger.warning("[audio-raw] ctx_mgr is None — dropping frame (%d bytes)", len(raw))
            return
        try:
            stream, seq, pcm = parse_audio_frame(raw)
        except ValueError:
            return
        try:
            if stream == "mic":
                speaker = "user"
                # Feed mic frames into the diarizer to build the user's voice profile.
                # Lazy-init: weights load on first audio frame, not at session startup.
                if self._diarizer is None:
                    self._diarizer = SpeakerDiarizer()
                self._diarizer.enroll_user(pcm)
            else:
                # System audio: use voice embeddings to detect echo/bleed vs interviewer.
                if self._diarizer is None:
                    self._diarizer = SpeakerDiarizer()
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

            # Emit each word individually so the frontend console shows word-by-word
            words = result.get("words") or []
            if words:
                for word in words:
                    await _safe_send(ws, {"type": "transcript_word", "speaker": speaker, "text": word, "seq": seq})

            # Utterance buffer — uses full text for context/AI
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
        # Lazy-init BERT on first call (loads weights once, then reused)
        if not self._bert_checked:
            try:
                self._bert = BertClassifier()
                self._use_bert = True
            except BertClassifierError:
                logger.warning("BERT unavailable — using silence detection fallback")
                self._use_bert = False
                self._bert = None
            self._bert_checked = True
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
        from app.core.cache import cache_set, cache_get

        session_id = session_ctx.get("_session_id", "unknown")
        q_hash = hashlib.md5(question_text.encode()).hexdigest() if question_text else ""

        # --- Suggestion cache (in-memory) ---
        cache_key = f"cluely:sugg_cache:{session_id}:{q_hash}" if q_hash else ""

        if cache_key:
            cached = await cache_get(cache_key)
            if cached:
                cached_response = cached.get("text", "")
                if cached_response:
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

            # Cache suggestion in-memory
            if cache_key and full_text:
                await cache_set(cache_key, {"text": full_text}, ttl=SUGGESTION_CACHE_TTL)

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
                cached = await cache_get(cache_key)
                if cached:
                    cached_text = cached.get("text", "")
                    if cached_text:
                        await _safe_send(ws, {"type": "suggestion_delta", "delta": cached_text})
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

        # Analyze immediately — stream tokens as they arrive
        mode = session_ctx.get("assessmentMode") or session_ctx.get("_assessment_mode")

        await _safe_send(ws, {"type": "status", "state": "thinking", "latency_ms": 0})

        t0 = time.monotonic()
        full_response: list[str] = []
        first = True

        try:
            async for delta in self._vision.stream_analyze(
                sid, mode=mode, session_ctx=session_ctx,
            ):
                if first:
                    latency = round((time.monotonic() - t0) * 1000)
                    await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": latency})
                    first = True
                full_response.append(delta)
                await _safe_send(ws, {"type": "suggestion_delta", "delta": delta})

            await _safe_send(ws, {"type": "suggestion_end"})

            full_text = "".join(full_response)
            if full_text:
                # Store this response so future screenshots don't repeat the same answer
                prev = session_ctx.setdefault("_vision_responses", [])
                prev.append(full_text[:300])
                if len(prev) > 5:
                    session_ctx["_vision_responses"] = prev[-5:]
        except Exception:
            logger.exception("Screenshot streaming error")
            await _safe_send(ws, {"type": "error", "code": "VISION_ERROR", "message": "Screenshot analysis failed"})

        await _safe_send(ws, {
            "type": "screenshot_result",
            "needs_more": False,
            "buffer_size": self._vision.buffer_size(sid),
            "cleared": self._vision.buffer_size(sid) == 0,
        })
        await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})

    # ------------------------------------------------------------------

    def _is_rate_limited(self, session_id: str, msg_type: str) -> bool:
        """
        Sliding-window rate limiter per (session, message type).
        Returns True if the caller should be throttled.
        """
        limit, window = _RATE_LIMITS.get(msg_type, (0, 60))
        if limit == 0:
            return False
        key = (session_id, msg_type)
        now = time.time()
        count, window_start = self._ask_rate.get(key, (0, now))
        if now - window_start >= window:
            count, window_start = 0, now
        if count >= limit:
            return True
        self._ask_rate[key] = (count + 1, window_start)
        return False

    @staticmethod
    def _needs_tools(text: str) -> bool:
        """
        Heuristic: does this message actually require tools (terminal, file, web search)?
        If not, we skip ChatAgent's non-streaming tool-loop and stream directly.
        """
        import re
        t = text.lower()
        # File path patterns (Windows or Unix)
        if re.search(r'[a-zA-Z]:\\|/home/|/usr/|/var/', text):
            return True
        # Explicit tool intent keywords
        tool_keywords = [
            "run ", "execute ", "npm ", "pip ", "python ", "node ",
            "search the web", "search online", "look up ", "google ",
            "read the file", "open the file", "write to ", "create a file",
            "ls ", "dir ", "git ", "docker ", "curl ", "wget ",
        ]
        return any(kw in t for kw in tool_keywords)

    async def _handle_manual_ask(self, ws, data: dict, session_ctx: dict, rag, ctx_mgr=None, repo=None):
        text = data.get("text", "")
        if not text:
            await _safe_send(ws, {"type": "error", "code": "INVALID_REQUEST", "message": "text is required"})
            return

        session_id = session_ctx.get("_session_id", "unknown")
        if self._is_rate_limited(session_id, "manual_ask"):
            await _safe_send(ws, {
                "type": "error",
                "code": "ASK_RATE_LIMITED",
                "message": f"Maximum {ASK_RATE_LIMIT} asks per minute reached.",
            })
            return

        t_ctx = time.monotonic()
        rag_chunks = await rag.retrieve(text, k=3) if rag else []
        if ctx_mgr:
            summary, facts = await asyncio.gather(ctx_mgr.get_summary(), ctx_mgr.get_facts())
        else:
            summary, facts = "", ""
        recent = session_ctx.get("_transcript_buf", [])[-15:]
        chat_history: list[dict] = data.get("history", [])
        mode = data.get("mode", "hints")
        logger.info("[manual_ask] context gathered in %dms | rag=%d | mode=%s | text=%r",
                    round((time.monotonic() - t_ctx) * 1000), len(rag_chunks), mode, text[:60])

        await _safe_send(ws, {"type": "status", "state": "thinking", "latency_ms": 0})
        t0 = time.monotonic()
        full_response: list[str] = []

        # ------------------------------------------------------------------
        # Fast path: conversational/interview questions — stream immediately,
        # no tool-loop blocking. Only use ChatAgent when tools are actually needed.
        # ------------------------------------------------------------------
        use_agent = self._needs_tools(text) or mode in ("solve", "ultra")
        logger.info("[manual_ask] use_agent=%s", use_agent)

        if not use_agent:
            try:
                first = True
                batch: list[str] = []
                async for delta in self._llm.stream_manual_ask(
                    text=text,
                    mode=mode,
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
            except LLMRateLimitedError:
                await _safe_send(ws, {"type": "error", "code": "LLM_RATE_LIMITED", "message": "Rate limited"})
                await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
            except Exception:
                logger.exception("Manual ask (fast path) error")
                await _safe_send(ws, {"type": "error", "code": "LLM_ERROR", "message": "Request failed"})
                await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
            return

        # ------------------------------------------------------------------
        # Tool path: ChatAgent with full ReAct loop
        # ------------------------------------------------------------------

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
            logger.exception("Manual ask (agent) error")
            await _safe_send(ws, {"type": "error", "code": "LLM_ERROR", "message": "Request failed"})
            await _safe_send(ws, {"type": "status", "state": "listening", "latency_ms": 0})
