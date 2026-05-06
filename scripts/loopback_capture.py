"""
loopback_capture.py — WASAPI loopback capture helper for Electron

Subcommands:
  list                         Print JSON array of loopback devices to stdout
  capture --device-id N        Stream raw int16 PCM to stdout until killed

Electron spawns this process; audio.ts reads stdout as PCM frames.
"""
import sys, json, struct, argparse

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd')

    sub.add_parser('list')

    cap = sub.add_parser('capture')
    cap.add_argument('--device-id', type=int, required=True)
    cap.add_argument('--rate',      type=int, default=48000)
    cap.add_argument('--channels',  type=int, default=2)

    args = parser.parse_args()

    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        sys.stderr.write('pyaudiowpatch not installed\n')
        sys.exit(1)

    pa = pyaudio.PyAudio()

    # ── list ──────────────────────────────────────────────────────────────
    if args.cmd == 'list':
        try:
            wasapi_idx = pa.get_host_api_info_by_type(pyaudio.paWASAPI)['index']
        except Exception:
            print('[]'); return

        results = []
        for i in range(pa.get_device_count()):
            d = pa.get_device_info_by_index(i)
            if d['hostApi'] != wasapi_idx:
                continue
            if d['maxInputChannels'] == 0:
                continue
            name = d['name']
            if '[Loopback]' in name or 'loopback' in name.lower():
                results.append({
                    'id':       d['index'],
                    'name':     name,
                    'rate':     int(d['defaultSampleRate']),
                    'channels': min(int(d['maxInputChannels']), 2),
                })
        print(json.dumps(results))
        sys.stdout.flush()

    # ── capture ───────────────────────────────────────────────────────────
    elif args.cmd == 'capture':
        device_id = args.device_id

        # Query the device's actual native rate and channel count from pyaudiowpatch
        try:
            dev_info  = pa.get_device_info_by_index(device_id)
            native_rate = int(dev_info['defaultSampleRate'])
            max_ch      = int(dev_info['maxInputChannels'])
        except Exception:
            native_rate = 48000
            max_ch      = 2

        channels = min(max_ch, 2) if max_ch > 0 else 2

        # Try native rate first, then common fallbacks
        candidate_rates = [native_rate] + [r for r in [48000, 44100, 16000] if r != native_rate]

        stream = None
        rate   = None
        for r in candidate_rates:
            try:
                stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=r,
                    input=True,
                    input_device_index=device_id,
                    frames_per_buffer=4096,
                )
                rate = r
                break
            except Exception as e:
                sys.stderr.write(f'rate {r} failed: {e}\n')
                sys.stderr.flush()

        if stream is None:
            sys.stderr.write(f'ERROR: Could not open device {device_id} at any sample rate\n')
            sys.stderr.flush()
            sys.exit(1)

        # Signal ready to Electron — include actual rate/channels so Electron can resample correctly
        sys.stderr.write(f'READY rate={rate} channels={channels}\n')
        sys.stderr.flush()

        out = sys.stdout.buffer
        try:
            while True:
                try:
                    data = stream.read(4096, exception_on_overflow=False)
                    out.write(data)
                    out.flush()
                except OSError as e:
                    sys.stderr.write(f'read error: {e} — stopping\n')
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
            pa.terminate()

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
