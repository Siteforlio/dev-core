from pydantic import BaseModel
from typing import Any, Literal


class ProfileUpsertRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    country: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    work_experience: list[dict[str, Any]] = []
    education: list[dict[str, Any]] = []
    skills: list[str] = []
    projects: list[dict[str, Any]] = []
    languages_spoken: list[dict[str, Any]] = []


class ResumeTextRequest(BaseModel):
    text: str


class CampaignCreateRequest(BaseModel):
    name: str
    # Single-select legacy fields (still accepted for backward compat)
    broad_category: str | None = None
    work_type: Literal["remote", "hybrid", "onsite", "any"] = "remote"
    # Multi-select fields (take priority when provided)
    categories: list[str] = []
    work_types: list[str] = []
    user_country: str | None = None  # None when anywhere=True
    anywhere: bool = False
    profile_overrides: dict[str, Any] = {}


class CampaignProfileUpsertRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    country: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    work_experience: list[dict[str, Any]] | None = None
    education: list[dict[str, Any]] | None = None
    skills: list[str] | None = None
    projects: list[dict[str, Any]] | None = None
    languages_spoken: list[dict[str, Any]] | None = None
    achievements: list[str] | None = None
    raw_context: str | None = None
    years_of_experience: int | None = None


class RawContextRequest(BaseModel):
    raw_context: str


class ManualJobRequest(BaseModel):
    title: str
    company: str
    description: str
    apply_url: str | None = None
    location: str | None = None


class CampaignStatusRequest(BaseModel):
    status: Literal["active", "paused", "archived"]


class EmailCredentialsRequest(BaseModel):
    host: str           # IMAP host e.g. imap.gmail.com
    port: int = 993
    username: str       # email address
    password: str       # app password or IMAP password
    smtp_host: str | None = None   # defaults to host if not provided
    smtp_port: int = 465


class CalDAVCredentialsRequest(BaseModel):
    url: str            # CalDAV endpoint e.g. https://caldav.icloud.com/
    username: str
    password: str


class LinkedInCredentialsRequest(BaseModel):
    # Option A — email/password (standard accounts)
    email: str | None = None
    password: str | None = None
    # Option B — session cookie (Google/SSO accounts)
    # Get from: linkedin.com → DevTools → Application → Cookies → li_at
    session_cookie: str | None = None

    def mode(self) -> str:
        if self.session_cookie:
            return "cookie"
        if self.email and self.password:
            return "password"
        raise ValueError("Provide either session_cookie or email+password")
