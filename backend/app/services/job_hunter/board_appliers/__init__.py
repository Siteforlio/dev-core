# board_appliers/__init__.py
"""
Per-board application submitters.

Each module exposes one class that subclasses BaseBoardApplier.
The dispatcher in apply_service.py uses get_applier(board_id) to
pick the right one at runtime.

Apply result contract
─────────────────────
Every apply() method returns an ApplyResult:
  success:  bool          — True = form submitted successfully
  skipped:  bool          — True = board doesn't support auto-apply (not a failure)
  reason:   str | None    — human-readable note for logging / UI
"""
from .base import BaseBoardApplier, ApplyResult
from .registry import get_applier, APPLIER_REGISTRY

__all__ = ["BaseBoardApplier", "ApplyResult", "get_applier", "APPLIER_REGISTRY"]
