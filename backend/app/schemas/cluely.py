from pydantic import BaseModel, Field
from typing import Literal


class SessionContext(BaseModel):
    job_title: str = ""
    company: str = ""
    resume_text: str = ""
    jd_text: str = ""
    files: list[str] = []
    # Optional link to a job_hunter application — creates FK in cluely_sessions
    application_id: str | None = None


class SessionStartRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    context: SessionContext


class TranscriptEntry(BaseModel):
    speaker: Literal["interviewer", "user"]
    text: str
    seq: int


class SuggestionResponse(BaseModel):
    delta: str
    done: bool


class ManualAskRequest(BaseModel):
    text: str
    mode: Literal["hints", "solve", "ultra"]
    language: str = "python"
