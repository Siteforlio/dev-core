"""
loopback_capture.py — Cross-platform system-audio loopback capture helper.

Subcommands
-----------
  list
      Print a JSON array of loopback/monitor devices to stdout.

  capture --device-id N [--rate R] [--channels C]
      Stream raw signed int16 PCM to stdout until killed.
      Writes "READY rate=R channels=C" to stderr once streaming begins
      so that the Electron parent process can set up its resampler.

Platform support
----------------
  Windows  → pyaudiowpatch (WASAPI loopback; detects [Loopback] sources)
  macOS    → pyaudio + CoreAudio (detects BlackHole / Soundflower / Loopback)
  Linux    → pyaudio + PulseAudio monitor sources (*.monitor devices)

Electron spawns this script; audio.ts reads stdout as raw PCM frames and
stderr for the READY signal.
"""
from __future__ import annotations

import json
import sys
import argparse

# ---------------------------------------------------------------------------
# Platform-aware PyAudio import
# ---------------------------------------------------------------------------
# pyaudiowpatch is a Windows-only fork that exposes WASAPI loopback streams.
# On macOS / Linux we fall back to the standard PyAudio package.

def _import_pyaudio():
    """Return (pyaudio module, is_wpatch: bool)."""
    if sys.platform == 'win32':
        try:
            import pyaudiowpatch as pa  # type: ignore
            return pa, True
        except ImportError:
            pass  # fall through to standard pyaudio
    try:
        import pyaudio as pa  # type: ignore
        return pa, False
    except ImportError:
        sys.stderr.write(
            'ERROR: No PyAudio backend found.\n'
            '  Windows : pip install pyaudiowpatch\n'
            '  macOS   : brew install portaudio && pip install pyaudio\n'
            '  Linux   : sudo apt install python3-pyaudio  # or pip install pyaudio\n'
        )
        sys.stderr.flush()
        sys.exit(1)


# ---------------------------------------------------------------------------
# Loopback device detection — per-platform name heuristics
# ---------------------------------------------------------------------------

_LOOPBACK_PATTERNS: dict[str, list[str]] = {
    # Windows: WASAPI appends "[Loopback]", or device is named "Stereo Mix" etc.
    'win32':  ['[Loopback]', 'loopback', 'stereo mix', 'what u hear', 'wave out'],
    # macOS: virtual audio devices that route system playback to an input.
    'darwin': ['blackhole', 'soundflower', 'loopback', 'virtual'],
    # Linux: PulseAudio monitor sources mirror playback sinks as inputs.
    'linux':  ['.monitor'],
}


def _is_loopback(name: str, is_wpatch: bool) -> bool:
    """Return True if the device name looks like a loopback/monitor source."""
    name_lower = name.lower()
    patterns = _LOOPBACK_PATTERNS.get(sys.platform, [])
    return any(p.lower() in name_lower for p in patterns)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(pa, is_wpatch: bool) -> None:
    """Print a JSON array of detected loopback devices."""
    results: list[dict] = []
    count = pa.PyAudio().get_device_count() if hasattr(pa, 'PyAudio') else 0

    instance = pa.PyAudio()
    try:
        for i in range(instance.get_device_count()):
            try:
                info = instance.get_device_info_by_index(i)
            except Exception:
                continue

            name: str = info.get('name', '')
            max_in: int = int(info.get('maxInputChannels', 0))

            if max_in == 0:
                continue
            if not _is_loopback(name, is_wpatch):
                continue

            results.append({
                'id':       i,
                'name':     name,
                'rate':     int(info.get('defaultSampleRate', 48000)),
                'channels': min(max_in, 2),
            })
    finally:
        instance.terminate()

    print(json.dumps(results))
    sys.stdout.flush()


def cmd_capture(pa, is_wpatch: bool, device_id: int, hint_rate: int, hint_channels: int) -> None:
    """Stream raw PCM from the given device to stdout."""
    instance = pa.PyAudio()

    # Resolve actual device capabilities.
    try:
        info = instance.get_device_info_by_index(device_id)
        native_rate: int = int(info.get('defaultSampleRate', hint_rate))
        max_in: int      = int(info.get('maxInputChannels', hint_channels))
    except Exception:
        native_rate = hint_rate
        max_in      = hint_channels

    channels = max(1, min(max_in, 2))

    # Try native rate first, then common fallbacks.
    candidate_rates = [native_rate] + [r for r in [48000, 44100, 16000] if r != native_rate]

    stream = None
    actual_rate: int = native_rate

    for rate in candidate_rates:
        try:
            stream = instance.open(
                format=pa.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=4096,
            )
            actual_rate = rate
            break
        except Exception as exc:
            sys.stderr.write(f'rate {rate} failed: {exc}\n')
            sys.stderr.flush()

    if stream is None:
        sys.stderr.write(
            f'ERROR: Could not open device {device_id} at any sample rate\n'
        )
        sys.stderr.flush()
        instance.terminate()
        sys.exit(1)

    # Signal Electron: actual rate and channel count so it can resample correctly.
    sys.stderr.write(f'READY rate={actual_rate} channels={channels}\n')
    sys.stderr.flush()

    out = sys.stdout.buffer
    try:
        while True:
            try:
                data = stream.read(4096, exception_on_overflow=False)
                out.write(data)
                out.flush()
            except OSError as exc:
                sys.stderr.write(f'read error: {exc} — stopping\n')
                sys.stderr.flush()
                break
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        instance.terminate()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Cross-platform system-audio loopback capture helper'
    )
    sub = parser.add_subparsers(dest='cmd')
    sub.add_parser('list', help='List loopback devices as JSON')

    cap = sub.add_parser('capture', help='Capture PCM from a loopback device')
    cap.add_argument('--device-id', type=int, required=True)
    cap.add_argument('--rate',      type=int, default=48000)
    cap.add_argument('--channels',  type=int, default=2)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    pa, is_wpatch = _import_pyaudio()

    if args.cmd == 'list':
        cmd_list(pa, is_wpatch)
    elif args.cmd == 'capture':
        cmd_capture(pa, is_wpatch, args.device_id, args.rate, args.channels)


if __name__ == '__main__':
    main()
