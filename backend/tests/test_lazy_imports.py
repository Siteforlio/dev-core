"""Verify heavy ML libraries are NOT imported at module level.

Each test runs in a subprocess so sys.modules is clean — no false passes.
"""
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])


def _assert_no_eager(module_path: str, blocked: list[str]):
    """Import module_path in a fresh process and assert blocked packages are not loaded."""
    script = f"""
import sys, importlib
before = set(sys.modules)
importlib.import_module("{module_path}")
after = set(sys.modules)
newly = after - before
for pkg in {blocked!r}:
    hits = [m for m in newly if m == pkg or m.startswith(pkg + ".")]
    if hits:
        print(f"FAIL: {{pkg}} loaded by {module_path}: {{hits[:5]}}")
        sys.exit(1)
print("OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=BACKEND_DIR,
    )
    assert result.returncode == 0, (
        f"Eager import detected:\n{result.stdout}{result.stderr}"
    )


def test_emotion_service_does_not_import_mediapipe():
    _assert_no_eager("app.services.emotion_service", ["mediapipe", "cv2"])


def test_emotion_router_does_not_import_mediapipe():
    _assert_no_eager("app.api.v1.emotion", ["mediapipe", "cv2"])
