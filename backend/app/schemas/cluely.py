from pydantic import BaseModel, Field, field_validator
from typing import Literal, Annotated


# ── Re-usable constrained types ──────────────────────────────────────────────
ShortStr   = Annotated[str, Field(max_length=256)]
MediumStr  = Annotated[str, Field(max_length=4000)]
LongStr    = Annotated[str, Field(max_length=8000)]
FilePath   = Annotated[str, Field(max_length=512)]


class SessionContext(BaseModel):
    job_title:      ShortStr  = ""
    company:        ShortStr  = ""
    resume_text:    LongStr   = ""
    jd_text:        MediumStr = ""
    files:          list[FilePath] = Field(default_factory=list, max_length=3)
    assessmentMode: ShortStr | None = None
    projectRoot:    FilePath  | None = None
    # Optional link to a job_hunter application
    application_id: str | None = Field(default=None, max_length=128)

    @field_validator("files", mode="before")
    @classmethod
    def limit_files(cls, v):
        if isinstance(v, list):
            return v[:3]
        return []


class SessionStartRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    context:    SessionContext = Field(default_factory=SessionContext)


class TranscriptEntry(BaseModel):
    speaker: Literal["interviewer", "user"]
    text:    str
    seq:     int


class SuggestionResponse(BaseModel):
    delta: str
    done:  bool


class ManualAskRequest(BaseModel):
    text:     str   = Field(..., max_length=2000)
    mode:     Literal["hints", "solve", "ultra", "chat"] = "chat"
    language: str   = Field(default="python", max_length=32)
    history:  list[dict] = Field(default_factory=list, max_length=50)
