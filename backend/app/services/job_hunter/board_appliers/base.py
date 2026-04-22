# board_appliers/base.py
"""
Base class for all per-board appliers.

Each applier receives:
  - url:     the specific apply_url for this job
  - ctx:     candidate context dict (name, email, resume_pdf, cover_letter, ...)
  - browser: BrowserService instance (already started)
  - page:    nodriver page already navigated to `url`

And returns an ApplyResult.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.job_hunter.browser_service import BrowserService


@dataclass
class ApplyResult:
    success: bool
    skipped: bool = False
    reason: str | None = None

    @classmethod
    def ok(cls, reason: str | None = None) -> "ApplyResult":
        return cls(success=True, skipped=False, reason=reason)

    @classmethod
    def fail(cls, reason: str) -> "ApplyResult":
        return cls(success=False, skipped=False, reason=reason)

    @classmethod
    def skip(cls, reason: str) -> "ApplyResult":
        return cls(success=False, skipped=True, reason=reason)


class BaseBoardApplier:
    """
    Override apply() in each subclass.

    The page passed in has already been navigated to the apply URL.
    Subclasses should NOT open a new browser — use the provided browser + page.
    """

    # Set in subclass to the board id this applier handles
    board_id: str = ""

    async def apply(
        self,
        url: str,
        ctx: dict,
        browser: "BrowserService",
        page,
    ) -> ApplyResult:
        raise NotImplementedError
