from pydantic import BaseModel
from typing import Any


class CreateSimSessionRequest(BaseModel):
    brief: dict[str, Any]
    attachments: list[dict[str, Any]] = []


class SimTurnRequest(BaseModel):
    content: str
    modality: str = "text"   # "voice" | "text"
    time_offset_seconds: int = 0


class SimSessionResponse(BaseModel):
    session_id: str
    persona: str
    time_budget_seconds: int | None = None
    scenario_type: str
    started_at: str


class SimTurnResponse(BaseModel):
    response: str
    tool_events: list[dict[str, Any]] = []
    time_remaining_seconds: int | None = None
    session_complete: bool = False
    cutoff: bool = False


# CoreScores documents the expected structure; dict used for flexibility
class CoreScores(BaseModel):
    communication: float
    time_management: float
    pressure_handling: float
    structure: float
    depth: float


class SimDebriefResponse(BaseModel):
    id: str
    session_id: str
    scenario_type: str | None = None
    overall_score: float | None = None
    hire_signal: str | None = None
    core_scores: dict[str, Any] | None = None
    scenario_scores: dict[str, Any] | None = None
    summary: str | None = None
    strengths: list[str]
    improvements: list[str]
    focus_areas: list[str]
    created_at: str
