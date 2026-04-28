from pydantic import BaseModel, Field
from typing import Literal


class SessionContext(BaseModel):
    job_title: str = ""
    company: str = ""
    resume_text: str = ""
    jd_text: str = ""
    files: list[str] = []


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
    mode: Literal["hints", "solve"]
    language: str = "python"  # for solve mode: caller passes detected or user-selected language
