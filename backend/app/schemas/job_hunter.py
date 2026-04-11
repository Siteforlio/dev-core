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
    broad_category: str
    user_country: str
    profile_overrides: dict[str, Any] = {}


class CampaignStatusRequest(BaseModel):
    status: Literal["active", "paused", "archived"]
