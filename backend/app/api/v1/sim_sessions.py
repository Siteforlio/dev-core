# backend/app/api/v1/sim_sessions.py
import asyncio
import base64
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.core.security import decode_token
from app.core.exceptions import InvalidCredentialsError
from app.core import ws_registry
from app.models.pg.simulation import SimulationSession, SimulationDebrief, SimulationTurn
from app.schemas.simulation import CreateSimSessionRequest
from app.services.simulation_engine import SimulationEngine, utcnow
from app.services.sim_llm_orchestrator import SimLLMOrchestrator
from app.services.sim_debrief_service import generate_pdf
from app.services.speech_service import SpeechService

router = APIRouter(prefix="/sim-sessions", tags=["simulation"])
logger = logging.getLogger(__name__)
bearer = HTTPBearer()


# ── Auth helpers ────────────────────────────────────────────────────────────

def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


async def _authenticate_ws(websocket: WebSocket, token: str | None) -> str | None:
    """Validate JWT before accepting WS. Returns user_id or closes with 4001."""
    if not token:
        await websocket.close(code=4001)
        return None
    try:
        return decode_token(token)
    except (InvalidCredentialsError, Exception):
        await websocket.close(code=4001)
        return None


# ── REST Endpoints ───────────────────────────────────────────────────────────

@router.post("")
async def create_sim_session(
    body: CreateSimSessionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    engine = SimulationEngine(db)
    session_data = await engine.create_session(
        user_id=user_id,
        brief=body.brief,
        attachments=body.attachments,
    )
    return {"data": session_data, "error": None}


@router.get("/{session_id}")
async def get_sim_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await db.execute(
        select(SimulationSession).where(SimulationSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"data": {
        "id": session.id,
        "scenario_type": session.scenario_type,
        "time_budget_seconds": session.time_budget_seconds,
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "hard_cutoff_fired": session.hard_cutoff_fired,
        "persona": session.persona,
    }, "error": None}


@router.post("/{session_id}/end")
async def end_sim_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await db.execute(select(SimulationSession).where(SimulationSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await db.execute(
        update(SimulationSession)
        .where(SimulationSession.id == session_id)
        .values(ended_at=utcnow())
    )
    await db.commit()
    engine = SimulationEngine(db)
    debrief = await engine.generate_debrief(session_id)
    return {"data": debrief, "error": None}


@router.post("/{session_id}/debrief")
async def trigger_debrief(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await db.execute(select(SimulationSession).where(SimulationSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    engine = SimulationEngine(db)
    debrief = await engine.generate_debrief(session_id)
    return {"data": debrief, "error": None}


@router.get("/{session_id}/debrief")
async def get_debrief(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await db.execute(
        select(SimulationSession).where(SimulationSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    result2 = await db.execute(
        select(SimulationDebrief).where(SimulationDebrief.session_id == session_id)
    )
    d = result2.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Debrief not yet generated")
    engine = SimulationEngine(db)
    return {"data": engine._debrief_to_dict(d), "error": None}


@router.get("/{session_id}/report")
async def get_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await db.execute(
        select(SimulationSession).where(SimulationSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    result2 = await db.execute(
        select(SimulationDebrief).where(SimulationDebrief.session_id == session_id)
    )
    d = result2.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Debrief not yet generated")
    engine = SimulationEngine(db)
    pdf_bytes = generate_pdf(engine._debrief_to_dict(d))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=sim-report-{session_id[:8]}.pdf"},
    )


# ── WebSocket ────────────────────────────────────────────────────────────────

@router.websocket("/{session_id}/ws")
async def sim_session_ws(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await _authenticate_ws(websocket, token)
    if user_id is None:
        return

    ws_registry.register(asyncio.current_task())
    await websocket.accept()

    # Fetch session metadata
    result = await db.execute(
        select(SimulationSession).where(SimulationSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        await websocket.send_json({"type": "error", "code": "NOT_FOUND", "message": "Session not found"})
        await websocket.close()
        return
    if session.user_id != user_id:
        await websocket.send_json({"type": "error", "code": "FORBIDDEN", "message": "Forbidden"})
        await websocket.close()
        return

    engine = SimulationEngine(db)
    speech = SpeechService()
    budget = session.time_budget_seconds
    started_at = session.started_at

    # Timer task — ticks every second, fires hard_cutoff at zero
    async def timer_loop():
        if not budget:
            return  # open-ended session — no timer needed
        try:
            while True:
                await asyncio.sleep(1)
                elapsed = (utcnow() - started_at).total_seconds()
                remaining = max(0, int(budget - elapsed))
                try:
                    await websocket.send_json({
                        "type": "timer_update",
                        "remaining_seconds": remaining,
                        "budget_seconds": budget,
                    })
                except Exception:
                    break
                if remaining == 0:
                    cutoff_msgs = {
                        "pitch": "Time. Stop right there.",
                        "mr_review": "Time's up. Let's debrief.",
                        "system_design": "Time. Wrap it up.",
                        "teaching": "Class time is over.",
                        "behavioral": "Time. Thank you.",
                        "negotiation": "Time. We'll pause here.",
                    }
                    msg = cutoff_msgs.get(session.scenario_type or "custom", "Time.")
                    try:
                        await websocket.send_json({"type": "hard_cutoff", "message": msg})
                        await websocket.send_json({"type": "session_end", "reason": "time_expired"})
                    except Exception:
                        pass
                    try:
                        async with AsyncSessionLocal() as cutoff_db:
                            await cutoff_db.execute(
                                update(SimulationSession)
                                .where(SimulationSession.id == session_id)
                                .values(hard_cutoff_fired=True)
                            )
                            await cutoff_db.commit()
                    except Exception as e:
                        logger.warning("[sim_ws] DB update failed on cutoff: %s", e)
                    break
        except asyncio.CancelledError:
            pass

    timer_task = asyncio.create_task(timer_loop())

    # In-memory turn cache — avoids DB read on every message as session grows
    turns_cache: list[dict] = []

    # Generate and send AI opening message, persist to DB so it survives reconnect
    try:
        _llm = SimLLMOrchestrator()
        await websocket.send_json({"type": "thinking", "active": True})
        opening = await _llm.opening_message(
            brief=session.brief or {},
            persona_note=session.persona or "",
        )
        opening_turn = SimulationTurn(
            session_id=session_id,
            seq=0,
            speaker="ai",
            modality="text",
            content=opening,
            time_offset_seconds=0,
        )
        db.add(opening_turn)
        await db.commit()
        turns_cache.append({"speaker": "ai", "content": opening, "time_offset_seconds": 0})
        await websocket.send_json({"type": "thinking", "active": False})
        await websocket.send_json({
            "type": "transcript", "speaker": "ai",
            "text": opening, "seq": 0, "final": True,
        })
        try:
            async for chunk in speech.synthesize_stream(opening):
                await websocket.send_json({
                    "type": "ai_audio",
                    "data": base64.b64encode(chunk).decode(),
                })
        except Exception as e:
            logger.warning("[sim_ws] TTS error on opening: %s", e)
    except Exception as e:
        logger.warning("[sim_ws] Failed to generate opening message: %s", e)
        await websocket.send_json({"type": "thinking", "active": False})

    # Audio buffer for voice turns
    audio_buf = bytearray()

    async def handle_user_turn(content: str, modality: str = "text") -> tuple[bool, bool]:
        """Process a user turn, get AI response, stream TTS. Returns (session_complete, cutoff)."""
        offset = int((utcnow() - session.started_at).total_seconds())
        turns_cache.append({"speaker": "user", "content": content, "time_offset_seconds": offset})
        await websocket.send_json({
            "type": "transcript", "speaker": "user",
            "text": content, "seq": 0, "final": True,
        })
        await websocket.send_json({"type": "thinking", "active": True})

        turn_result = await engine.submit_turn(
            session_id=session_id,
            content=content,
            modality=modality,
            time_offset_seconds=offset,
            cached_turns=turns_cache[:-1],
        )

        for te in turn_result.get("tool_events", []):
            await websocket.send_json({"type": "tool_event", **te})

        ai_text = turn_result.get("response", "")
        turns_cache.append({
            "speaker": "ai", "content": ai_text,
            "time_offset_seconds": int((utcnow() - session.started_at).total_seconds()),
        })
        await websocket.send_json({"type": "thinking", "active": False})
        await websocket.send_json({
            "type": "transcript", "speaker": "ai",
            "text": ai_text, "seq": 1, "final": True,
        })

        try:
            async for chunk in speech.synthesize_stream(ai_text):
                await websocket.send_json({
                    "type": "ai_audio",
                    "data": base64.b64encode(chunk).decode(),
                })
        except Exception as e:
            logger.warning("[sim_ws] TTS error: %s", e)

        return bool(turn_result.get("session_complete")), bool(turn_result.get("cutoff"))

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "text_turn":
                content = msg.get("content", "").strip()
                if not content:
                    continue
                done, cutoff = await handle_user_turn(content, modality="text")
                if done or cutoff:
                    timer_task.cancel()
                    await websocket.send_json({
                        "type": "session_end",
                        "reason": "time_expired" if cutoff else "ai_ended",
                    })
                    break

            elif msg_type == "audio_chunk":
                # Accumulate raw audio bytes from the browser MediaRecorder
                raw = base64.b64decode(msg.get("data", ""))
                audio_buf.extend(raw)

            elif msg_type == "audio_flush":
                # User stopped speaking — transcribe accumulated buffer
                if not audio_buf:
                    continue
                buf_copy = bytes(audio_buf)
                audio_buf.clear()
                try:
                    transcript = await speech.transcribe(buf_copy)
                except Exception as e:
                    logger.warning("[sim_ws] Transcription error: %s", e)
                    transcript = ""
                if not transcript:
                    continue
                done, cutoff = await handle_user_turn(transcript, modality="voice")
                if done or cutoff:
                    timer_task.cancel()
                    await websocket.send_json({
                        "type": "session_end",
                        "reason": "time_expired" if cutoff else "ai_ended",
                    })
                    break

            elif msg_type == "end_session":
                timer_task.cancel()
                await websocket.send_json({"type": "session_end", "reason": "user_ended"})
                break

    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        timer_task.cancel()
        try:
            await timer_task
        except asyncio.CancelledError:
            pass
