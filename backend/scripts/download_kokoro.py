"""
One-time script to download Kokoro ONNX model files.

Run from the project root:
    python backend/scripts/download_kokoro.py
"""
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models" / "kokoro"

FILES = {
    "kokoro-v0_19.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
    "voices.bin":         "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin",
}


def _download(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  ✓ {dest.name} already exists — skipping")
        return
    print(f"  ↓ Downloading {dest.name} …")
    urllib.request.urlretrieve(url, dest)
    print(f"  ✓ {dest.name} saved ({dest.stat().st_size // 1_048_576} MB)")


if __name__ == "__main__":
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Kokoro model directory: {MODELS_DIR}\n")
    for filename, url in FILES.items():
        _download(url, MODELS_DIR / filename)
    print("\nDone. Start the backend and Kokoro TTS will load on first use.")
