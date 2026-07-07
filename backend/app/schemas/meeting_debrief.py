from pydantic import BaseModel
from typing import Any


class ActionItemSchema(BaseModel):
    text: str
    owner: str = ""
    due: str = ""
    done: bool = False


class DecisionSchema(BaseModel):
    text: str
    meta: str = ""


class AttendeeSchema(BaseModel):
    name: str
    email: str = ""
    role: str = ""
    initials: str = ""
    color: str = "#22d3ee"
    status: str = "present"


class MeetingDebriefCreateRequest(BaseModel):
    calendar_event_uid: str | None = None
    date: str | None = None          # YYYY-MM-DD
    title: str = "Untitled meeting"
    location: str | None = None
    start_time: str | None = None    # HH:MM
    duration_minutes: int | None = None
    attendees: list[AttendeeSchema] = []


class MeetingDebriefPatchRequest(BaseModel):
    notes: str | None = None
    actions: list[dict[str, Any]] | None = None
    decisions: list[dict[str, Any]] | None = None
    attendees: list[dict[str, Any]] | None = None
    title: str | None = None
    cluely_session_id: str | None = None


class MeetingDebriefResponse(BaseModel):
    id: str
    calendar_event_uid: str | None
    cluely_session_id: str | None
    date: str | None
    title: str
    location: str | None
    start_time: str | None
    duration_minutes: int | None
    notes: str | None
    actions: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    attendees: list[dict[str, Any]]
    ai_summary: str | None
    ai_summary_status: str
    updated_at: str
