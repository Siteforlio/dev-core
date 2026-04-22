# board_appliers/no_apply.py
"""
No-auto-apply boards — boards where automated application is not feasible.

LinkedIn:    Explicitly skipped (Easy Apply needs full LinkedIn session flow)
HN Hiring:   Mostly email addresses or bare career pages — not automatable
Kuhustle:    Freelance gig platform — not a standard job apply flow
Zindi:       Data science competition platform — no standard apply form
"""
from __future__ import annotations
from .base import BaseBoardApplier, ApplyResult


class LinkedInApplier(BaseBoardApplier):
    board_id = "linkedin"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        return ApplyResult.skip(
            "LinkedIn Easy Apply requires a full LinkedIn browser session. "
            "Apply manually at: " + url
        )


class HNHiringApplier(BaseBoardApplier):
    board_id = "hn_hiring"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        return ApplyResult.skip(
            "HN Who's Hiring jobs are typically email applications or bare career links. "
            "Apply manually at: " + url
        )


class KuhusteApplier(BaseBoardApplier):
    board_id = "kuhustle"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        return ApplyResult.skip(
            "Kuhustle is a freelance gig platform with no standard job application form. "
            "Apply manually at: " + url
        )


class ZindiApplier(BaseBoardApplier):
    board_id = "zindi"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        return ApplyResult.skip(
            "Zindi is a data science competition platform — applications are competition entries, "
            "not standard job forms. Apply manually at: " + url
        )
