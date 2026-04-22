# board_appliers/registry.py
"""
Maps board_id → BaseBoardApplier instance.

Applier instances are singletons (stateless) — safe to share across calls.
"""
from __future__ import annotations
from .base import BaseBoardApplier, ApplyResult
from .greenhouse   import GreenhouseApplier
from .lever        import LeverApplier
from .ashby        import AshbyApplier
from .fuzu         import FuzuApplier
from .brightermonday import BrighterMondayApplier
from .andela       import AndelaApplier
from .arc          import ArcApplier
from .redirect_apply import RedirectApplier
from .no_apply     import LinkedInApplier, HNHiringApplier, KuhusteApplier, ZindiApplier


# ── Registry ──────────────────────────────────────────────────────────────────

APPLIER_REGISTRY: dict[str, BaseBoardApplier] = {
    # ATS — full auto-apply
    "greenhouse":         GreenhouseApplier(),
    "lever":              LeverApplier(),
    "ashby":              AshbyApplier(),

    # Aggregators / startup boards — redirect to company ATS then fill
    "indeed":             RedirectApplier("indeed"),
    "glassdoor":          RedirectApplier("glassdoor"),
    "zip_recruiter":      RedirectApplier("zip_recruiter"),
    "google":             RedirectApplier("google"),
    "remotive":           RedirectApplier("remotive"),
    "remoteok":           RedirectApplier("remoteok"),
    "weworkremotely":     RedirectApplier("weworkremotely"),
    "startupdeals_africa":RedirectApplier("startupdeals_africa"),
    "myjobmag":           RedirectApplier("myjobmag"),

    # Kenya / Africa native platforms
    "fuzu":               FuzuApplier(),
    "brightermonday":     BrighterMondayApplier(),
    "andela":             AndelaApplier(),
    "arc":                ArcApplier(),

    # No auto-apply
    "linkedin":           LinkedInApplier(),
    "hn_hiring":          HNHiringApplier(),
    "kuhustle":           KuhusteApplier(),
    "zindi":              ZindiApplier(),
}

# Universal fallback for any board not in the registry
_UNIVERSAL_BOARDS = {"workday", "generic"}


def get_applier(board_id: str) -> BaseBoardApplier:
    """
    Return the applier for a given board_id.

    Falls back to a RedirectApplier (universal filler) for unknown boards
    rather than raising — handles Workday and any future boards gracefully.
    """
    if board_id in APPLIER_REGISTRY:
        return APPLIER_REGISTRY[board_id]
    # Unknown board — treat as generic redirect/universal
    return RedirectApplier(board_id)
