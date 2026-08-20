import * as naudiodon from 'naudiodon'
import WebSocket from 'ws'
import path from 'path'
import { spawn, ChildProcess } from 'child_process'
import { Worker } from 'worker_threads'
import { getOverlayWindow } from './overlay'

const PROJECT_ROOT = path.join(__dirname, '..')

// Platform-aware venv Python path.
// Windows: venv\Scripts\python.exe
// macOS / Linux: venv/bin/python3
const PYTHON_EXE = process.platform === 'win32'
  ? path.join(PROJECT_ROOT, 'backend', 'venv', 'Scripts', 'python.exe')
  : path.join(PROJECT_ROOT, 'backend', 'venv', 'bin', 'python3')

const LOOPBACK_SCRIPT = path.join(PROJECT_ROOT, 'scripts', 'loopback_capture.py')

let micInput: naudiodon.IoStreamRead | null = null
let sysInput: naudiodon.IoStreamRead | null = null
let sysProc: ChildProcess | null = null   // Python loopback process
let ws: WebSocket | null = null
let chunkSeq = 0

// Reconnection state — cleared on explicit stopAudioCapture()
let _reconnectAttempts = 0
let _reconnectTimer: ReturnType<typeof setTimeout> | null = null
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BASE_DELAY_MS = 1000  // doubles each attempt: 1s, 2s, 4s, 8s, 16s

// Capture args so reconnect can re-open the same session
let _lastArgs: { wsUrl: string; token: string; audioSource: 'mic' | 'system' | 'both'; sessionId: string; context: Record<string, unknown>; micDeviceId: number | null; sysDeviceId: number | null } | null = null

// Forward a parsed backend frame to the overlay renderer window.
function forwardToOverlay(frame: Record<string, unknown>) {
  const win = getOverlayWindow()
  if (!win || win.isDestroyed()) return

  const type = frame.type as string
  switch (type) {
    case 'suggestion_delta':
      win.webContents.send('devcore:suggestion', { delta: frame.delta, done: false })
      break
    case 'suggestion_end':
      win.webContents.send('devcore:suggestion', { delta: '', done: true })
      break
    case 'transcript':
      win.webContents.send('devcore:transcript', {
        speaker: frame.speaker,
        text: frame.text,
        seq: frame.seq,
      })
      break
    case 'transcript_word':
      win.webContents.send('devcore:transcript:word', {
        speaker: frame.speaker,
        text: frame.text,
      })
      break
    case 'status':
      win.webContents.send('devcore:status', {
        state: frame.state,
        latencyMs: frame.latency_ms ?? 0,
      })
      break
    case 'error':
      win.webContents.send('devcore:error', { code: frame.code, message: frame.message })
      break
    case 'code_result':
      win.webContents.send('devcore:suggestion', {
        delta: `\n\n**Output:**\n\`\`\`\n${frame.output}\n\`\`\``,
        done: true,
      })
      break
    case 'outcome_inferred':
      win.webContents.send('devcore:outcome', {
        outcome: frame.outcome,
        question: frame.question,
      })
      break
    case 'session_title':
      win.webContents.send('devcore:session:title', { title: frame.title })
      break
    case 'tool:event':
      win.webContents.send('devcore:tool:event', {
        tool:   frame.tool,
        status: frame.status,
        data:   frame.data ?? {},
      })
      break
    case 'agent:thinking':
      win.webContents.send('devcore:agent:thinking', { text: frame.text })
      break
    case 'agent:guidance':
      win.webContents.send('devcore:agent:guidance', { text: frame.text })
      break
    case 'agent:solution':
      win.webContents.send('devcore:agent:solution', {
        code:        frame.code,
        language:    frame.language,
        explanation: frame.explanation,
      })
      break
    case 'screenshot_buffered':
      win.webContents.send('devcore:screenshot:count', { count: frame.count })
      break
    case 'screenshot_cleared':
      win.webContents.send('devcore:screenshot:count', { count: 0 })
      break
    case 'screenshot_result':
      win.webContents.send('devcore:screenshot:result', {
        needsMore:  frame.needs_more,
        bufferSize: frame.buffer_size,
        cleared:    frame.cleared,
      })
      break
  }
}

export function startAudioCapture(
  wsUrl: string,
  token: string,
  audioSource: 'mic' | 'system' | 'both',
  sessionId: string,
  context: Record<string, unknown>,
  micDeviceId: number | null = null,
  sysDeviceId: number | null = null,
) {
  stopAudioCapture()
  _reconnectAttempts = 0
  _lastArgs = { wsUrl, token, audioSource, sessionId, context, micDeviceId, sysDeviceId }
  _openWebSocket(wsUrl, token, audioSource, sessionId, context, micDeviceId, sysDeviceId)
}

function _stopStreams(reason?: string) {
  if (reason) console.log(`[devcore-audio] _stopStreams called: ${reason}`)
  else console.log(`[devcore-audio] _stopStreams called`, new Error().stack?.split('\n')[2]?.trim())
  // Terminate any attached DSP workers before stopping the stream
  for (const stream of [micInput, sysInput]) {
    const worker = stream && (stream as any)._dspWorker
    if (worker) { try { worker.terminate() } catch { /* already gone */ } }
  }
  try { micInput?.quit() } catch { /* already stopped */ }
  try { sysInput?.quit() } catch { /* already stopped */ }
  if (sysProc) { try { sysProc.kill() } catch { /* already dead */ }; sysProc = null }
  micInput = sysInput = null
}

// Start system audio capture via pyaudiowpatch subprocess.
// Returns the ChildProcess so _stopStreams can kill it.
function _startPythonLoopback(deviceId: number, rate: number, channels: number): ChildProcess | null {
  try {
    const proc = spawn(PYTHON_EXE, [
      LOOPBACK_SCRIPT, 'capture',
      '--device-id', String(deviceId),
      '--rate',      String(rate),
      '--channels',  String(channels),
    ])

    // VAD state — rate/channels may be updated when Python signals READY
    const FRAME_MS         = 30
    const SPEECH_THRESHOLD = 0.004
    const SILENCE_FLUSH    = 10
    let MIN_BYTES          = rate * 0.15 * 2
    let FRAME_BYTES        = Math.floor(rate * FRAME_MS / 1000) * channels * 2

    let rawBuf       = Buffer.alloc(0)
    let speechBuf    = Buffer.alloc(0)
    let silentFrames = 0
    let inSpeech     = false

    proc.stdout?.on('data', (chunk: Buffer) => {
      // Always consume the pipe even when WS isn't ready — if we return early
      // the OS pipe buffer fills (~64KB), Python's write() blocks, and the
      // process gets killed with code=null.
      if (!ws || ws.readyState !== 1) return  // discard but pipe was already drained
      rawBuf = Buffer.concat([rawBuf, chunk])

      while (rawBuf.length >= FRAME_BYTES) {
        const frame = rawBuf.subarray(0, FRAME_BYTES)
        rawBuf = rawBuf.subarray(FRAME_BYTES)

        // stereo → mono
        let mono: Buffer
        if (channels === 2) {
          const frames = Math.floor(frame.length / 4)
          mono = Buffer.alloc(frames * 2)
          for (let i = 0; i < frames; i++) {
            const l = frame.readInt16LE(i * 4)
            const r = frame.readInt16LE(i * 4 + 2)
            mono.writeInt16LE(Math.round((l + r) / 2), i * 2)
          }
        } else {
          mono = frame
        }

        // resample to 16kHz
        let pcm: Buffer
        if (rate !== 16000) {
          const ratio     = rate / 16000
          const inSamples = mono.length / 2
          const outCount  = Math.floor(inSamples / ratio)
          pcm = Buffer.alloc(outCount * 2)
          for (let i = 0; i < outCount; i++) {
            const src = Math.min(Math.round(i * ratio), inSamples - 1)
            pcm.writeInt16LE(mono.readInt16LE(src * 2), i * 2)
          }
        } else {
          pcm = mono
        }

        // RMS
        const samples = pcm.length / 2
        let sumSq = 0
        for (let i = 0; i < samples; i++) {
          const s = pcm.readInt16LE(i * 2) / 32768.0
          sumSq += s * s
        }
        const rms = Math.sqrt(sumSq / samples)

        if (rms >= SPEECH_THRESHOLD) {
          speechBuf    = Buffer.concat([speechBuf, pcm])
          silentFrames = 0
          inSpeech     = true
        } else if (inSpeech) {
          speechBuf    = Buffer.concat([speechBuf, pcm])
          silentFrames++
          if (silentFrames >= SILENCE_FLUSH) {
            if (speechBuf.length >= MIN_BYTES) {
              const sock = ws
              if (sock && sock.readyState === 1) {
                const seq    = chunkSeq++ % 65536
                const header = Buffer.alloc(3)
                header.writeUInt8(0x02, 0)
                header.writeUInt16BE(seq, 1)
                try { sock.send(Buffer.concat([header, speechBuf])) } catch { /* closed */ }
              }
            }
            speechBuf    = Buffer.alloc(0)
            silentFrames = 0
            inSpeech     = false
          }
        }
      }
    })

    proc.stderr?.on('data', (d: Buffer) => {
      const msg = d.toString().trim()
      console.log('[devcore-loopback]', msg)
      // Parse READY line to get actual rate/channels — update VAD frame size
      const m = msg.match(/READY rate=(\d+) channels=(\d+)/)
      if (m) {
        rate     = parseInt(m[1])
        channels = parseInt(m[2])
        FRAME_BYTES = Math.floor(rate * FRAME_MS / 1000) * channels * 2
        MIN_BYTES   = rate * 0.2 * 2
        console.log(`[devcore-loopback] stream ready @ ${rate} Hz ${channels}ch`)
      }
    })
    proc.on('exit', (code) => {
      console.log(`[devcore-loopback] process exited code=${code}`)
      if (sysProc === proc) sysProc = null
    })
    proc.on('error', (err) => {
      console.error('[devcore-loopback] spawn error:', err.message)
    })

    console.log(`[devcore-audio] Python loopback started — device ${deviceId} @ ${rate} Hz ${channels}ch`)
    return proc
  } catch (err) {
    console.error('[devcore-audio] Failed to start Python loopback:', err)
    return null
  }
}

function _scheduleReconnect() {
  if (_reconnectAttempts >= MAX_RECONNECT_ATTEMPTS || !_lastArgs) return
  _stopStreams()   // kill audio streams before reconnecting so they don't send to next socket
  const delay = RECONNECT_BASE_DELAY_MS * Math.pow(2, _reconnectAttempts)
  _reconnectAttempts++
  console.log(`[devcore-audio] Reconnecting in ${delay}ms (attempt ${_reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`)
  const win = getOverlayWindow()
  win?.webContents.send('devcore:status', { state: 'reconnecting', latencyMs: 0 })
  _reconnectTimer = setTimeout(() => {
    _reconnectTimer = null
    if (!_lastArgs) return
    const { wsUrl, token, audioSource, sessionId, context, micDeviceId, sysDeviceId } = _lastArgs
    _openWebSocket(wsUrl, token, audioSource, sessionId, context, micDeviceId, sysDeviceId)
  }, delay)
}

function _openWebSocket(
  wsUrl: string,
  token: string,
  audioSource: 'mic' | 'system' | 'both',
  sessionId: string,
  context: Record<string, unknown>,
  micDeviceId: number | null = null,
  sysDeviceId: number | null = null,
) {
  ws = new WebSocket(wsUrl)

  const localWs = ws  // capture ref before any async nulling
  localWs.on('open', () => {
    if (!localWs || localWs.readyState !== 1) return
    _reconnectAttempts = 0  // reset on successful connect
    console.log(`[devcore-audio] WS open — sending auth, token=${token ? token.slice(0,20)+'…' : 'EMPTY'}`)
    try {
      localWs.send(JSON.stringify({ type: 'auth', token }))
      localWs.send(JSON.stringify({
        type: 'session_start',
        session_id: sessionId,
        context: {
          job_title:       (context as any).jobTitle       ?? '',
          company:         (context as any).company        ?? '',
          resume_text:     (context as any).resumeText     ?? '',
          jd_text:         (context as any).jdText         ?? '',
          files:           (context as any).files          ?? [],
          assessmentMode:  (context as any).assessmentMode ?? null,
          projectRoot:     (context as any).projectRoot    ?? null,
        },
      }))
    } catch (e) {
      console.error('[devcore-audio] Failed to send handshake:', e)
    }
  })

  localWs.on('message', (raw: Buffer | string) => {
    try {
      const frame = JSON.parse(raw.toString())
      forwardToOverlay(frame)
    } catch {
      // binary frames (audio echo etc.) — ignore
    }
  })

  localWs.on('error', (err: Error) => {
    console.error('[devcore-audio] WS error:', err.message)
    const win = getOverlayWindow()
    win?.webContents.send('devcore:error', { code: 'WS_ERROR', message: err.message })
    // Don't call stopAudioCapture() here — let 'close' fire and handle reconnect
  })

  localWs.on('close', (code: number) => {
    console.log(`[devcore-audio] WS closed code=${code}`)
    // 1000 = normal closure, 4001 = auth — don't surface these as errors to the user
    if (code !== 1000 && code !== 4001) {
      const win = getOverlayWindow()
      win?.webContents.send('devcore:error', { code: `WS_CLOSED_${code}`, message: `WebSocket closed with code ${code}` })
    }
    // Only act if this is still the active socket (guard against stale close events)
    if (ws === localWs) ws = null
    // 1000 = normal closure (user called endSession/pause), 4001 = auth failure — don't reconnect
    const intentional = code === 1000 || code === 4001 || _lastArgs === null
    if (!intentional) {
      console.log(`[devcore-audio] WS closed unexpectedly (code=${code}) — scheduling reconnect`)
      _scheduleReconnect()  // _scheduleReconnect stops streams itself
    } else {
      _stopStreams(`WS closed intentionally code=${code}`)
    }
  })

  // Audio device setup — wrapped so a naudiodon failure doesn't kill the WS session.
  try {
    const devices: any[] = naudiodon.getDevices()

    // Platform-preferred host APIs (ordered by preference).
    // naudiodon surfaces multiple backends; we pick the most direct one per OS.
    const PREFERRED_APIS: Record<string, string[]> = {
      win32:  ['Windows WASAPI', 'Windows DirectSound', 'Windows MME'],
      darwin: ['Core Audio'],
      linux:  ['ALSA', 'PulseAudio', 'Jack Audio Connection Kit'],
    }
    const preferredApis = PREFERRED_APIS[process.platform] ?? []

    // Pick the best available host API for this platform.
    const bestApi = preferredApis.find(api =>
      devices.some((d: any) => d.hostAPIName === api)
    ) ?? null

    const platformDevices = bestApi
      ? devices.filter((d: any) => d.hostAPIName === bestApi)
      : devices  // fallback: accept all APIs

    console.log(`[devcore-audio] Platform=${process.platform} | Best API="${bestApi ?? 'any'}" | Devices:`)
    platformDevices.forEach((d: any) =>
      console.log(`  [${d.id}] "${d.name}" | inputs=${d.maxInputChannels} | loopback=${d.isLoopbackDevice}`)
    )

    // Loopback device detection — patterns differ per OS:
    //   Windows : WASAPI loopback, Stereo Mix, "What U Hear", "[Loopback]" suffix
    //   macOS   : BlackHole, Soundflower, Loopback (Rogue Amoeba), Virtual
    //   Linux   : PulseAudio monitor sources (.monitor suffix)
    const isLoopbackDevice = (d: any): boolean =>
      d.isLoopbackDevice === true ||
      (d.maxInputChannels > 0 && /loopback|stereo mix|what u hear|wave out|\[loopback\]|blackhole|soundflower|virtual|\.monitor/i.test(d.name))

    const loopback = platformDevices.find((d: any) => isLoopbackDevice(d)) ?? null
    const mic = platformDevices.find((d: any) =>
      d.maxInputChannels > 0 && !isLoopbackDevice(d)
    ) ?? null

    console.log(
      `[devcore-audio] mic=[${micDeviceId ?? mic?.id ?? 'none'}] "${mic?.name ?? 'none'}" | ` +
      `loopback=[${sysDeviceId ?? loopback?.id ?? 'none'}] "${loopback?.name ?? 'none found'}"`
    )

    const TARGET_RATE     = 16000
    const CANDIDATE_RATES = [48000, 44100, 16000]

    // VAD parameters
    const FRAME_MS             = 30      // RMS measured per this window
    const SPEECH_RMS_THRESHOLD = 0.004  // above = speech
    const SILENCE_FRAMES_FLUSH = 10     // ~300ms pause → flush utterance
    const MIN_SPEECH_BYTES     = TARGET_RATE * 0.15 * 2  // 150ms minimum utterance
    const MIC_GAIN             = 4.0    // software boost for quiet headset mics

    function sendChunk(pcm: Buffer, streamId: 0x01 | 0x02) {
      const sock = ws
      if (!sock || sock.readyState !== 1) {
        console.log(`[devcore-audio] sendChunk: WS not ready (state=${sock?.readyState ?? 'null'}) — dropping ${pcm.length}B`)
        return
      }
      const seq = chunkSeq++ % 65536
      const header = Buffer.alloc(3)
      header.writeUInt8(streamId, 0)
      header.writeUInt16BE(seq, 1)
      console.log(`[devcore-audio] sendChunk: stream=0x${streamId.toString(16)} seq=${seq} bytes=${pcm.length}`)
      try { sock.send(Buffer.concat([header, pcm])) } catch { /* socket closed mid-send */ }
    }

    // Resolve the compiled worker path. In development ts-node runs from source;
    // in the packaged app the worker is compiled alongside the main process.
    const WORKER_PATH = path.join(__dirname, 'audio-worker.js')

    function startStream(deviceId: number, streamId: 0x01 | 0x02): naudiodon.IoStreamRead | null {
      const deviceInfo = naudiodon.getDevices().find((d: any) => d.id === deviceId) as any
      const maxCh: number = deviceInfo?.maxInputChannels ?? 2
      const CHANNELS = maxCh >= 2 ? 2 : 1
      const isMic = streamId === 0x01
      const gain  = isMic ? MIC_GAIN : 1.0

      for (const captureRate of CANDIDATE_RATES) {
        try {
          const FRAME_BYTES_RAW = Math.floor((captureRate * FRAME_MS) / 1000) * CHANNELS * 2

          const input = naudiodon.AudioIO({
            inOptions: {
              deviceId,
              channelCount: CHANNELS,
              sampleRate: captureRate,
              framesPerBuffer: 4096,
              sampleFormat: naudiodon.SampleFormat16Bit,
            }
          })

          // Spawn a dedicated worker thread for all DSP (resample, VAD, gain)
          const worker = new Worker(WORKER_PATH)
          worker.postMessage({ type: 'init', channels: CHANNELS, captureRate, gain, streamId, isMic })

          worker.on('message', (msg: { type: string; rms?: number; buf?: ArrayBuffer; streamId?: number }) => {
            if (msg.type === 'audio_level' && msg.rms !== undefined) {
              const win = getOverlayWindow()
              if (win && !win.isDestroyed()) {
                win.webContents.send('devcore:audio:level', { rms: msg.rms })
              }
            } else if (msg.type === 'speech_chunk' && msg.buf) {
              console.log(`[devcore-audio] worker speech_chunk: ${msg.buf.byteLength}B stream=0x${streamId.toString(16)}`)
              sendChunk(Buffer.from(msg.buf), streamId)
            }
          })

          worker.on('error', (err: Error) => {
            console.error('[devcore-audio] worker error:', err.message)
          })

          input.on('data', (chunk: Buffer) => {
            if (!ws || ws.readyState !== 1) return
            // Transfer the raw audio to the worker — zero-copy via ArrayBuffer transfer
            const ab = chunk.buffer.slice(chunk.byteOffset, chunk.byteOffset + chunk.byteLength)
            worker.postMessage({ type: 'frame', buf: ab }, [ab as ArrayBuffer])
          })

          input.on('error', (err: Error) => {
            console.error('[devcore-audio] stream error:', err.message)
            worker.terminate()
          })

          // Attach the worker to the stream so stopAudioCapture can terminate it
          ;(input as any)._dspWorker = worker

          input.start()
          console.log(`[devcore-audio] Device ${deviceId} (${isMic ? 'mic' : 'system'}) started @ ${captureRate} Hz gain=${gain} (worker DSP)`)
          return input
        } catch (err) {
          console.warn(`[devcore-audio] Device ${deviceId} rejected ${captureRate} Hz:`, (err as Error).message)
        }
      }
      console.error(`[devcore-audio] Device ${deviceId} rejected all sample rates — skipping`)
      return null
    }

    if ((audioSource === 'system' || audioSource === 'both')) {
      const sysId = sysDeviceId ?? loopback?.id
      if (sysId != null) {
        if (process.platform === 'win32') {
          // On Windows, always use pyaudiowpatch for loopback capture.
          // naudiodon opens WASAPI loopback devices but captures silence —
          // pyaudiowpatch is specifically designed for WASAPI loopback.
          const devInfo = devices.find((d: any) => d.id === sysId) as any
          const rate    = devInfo?.defaultSampleRate ?? 48000
          const ch      = Math.min(devInfo?.maxInputChannels ?? 2, 2) || 2
          sysProc = _startPythonLoopback(sysId, Math.round(rate), ch)
        } else {
          sysInput = startStream(sysId, 0x02)
        }
      }
    }
    if ((audioSource === 'mic' || audioSource === 'both')) {
      const micId = micDeviceId ?? mic?.id
      if (micId != null) micInput = startStream(micId, 0x01)
    }

    if (!loopback && !mic) {
      console.warn('[devcore-audio] No WASAPI devices found — session running without audio capture')
    }
  } catch (err) {
    console.error('[devcore-audio] Audio device setup failed (session continues without audio):', err)
  }
}

export function stopAudioCapture() {
  // Clear reconnect state first so the close handler doesn't schedule another attempt
  _lastArgs = null
  if (_reconnectTimer !== null) { clearTimeout(_reconnectTimer); _reconnectTimer = null }
  _reconnectAttempts = 0
  _stopStreams()
  ws?.close(1000)   // explicit 1000 = intentional, suppresses reconnect in close handler
  ws = null
  chunkSeq = 0
}

export function getActiveWs() { return ws }

/**
 * Capture a screenshot of the primary display and send it to the backend
 * over the active WebSocket as a screenshot_frame message.
 * Returns the buffer count reported by the backend (via the reply message),
 * or -1 if the WS is not open or capture fails.
 */
export async function captureAndSendScreenshot(): Promise<number> {
  const sock = ws
  if (!sock || sock.readyState !== 1) {
    console.warn('[devcore-screenshot] No active WS — ignoring')
    return -1
  }

  try {
    // desktopCapturer is only available in the main process — this function
    // runs in the main process via IPC (see main.ts), so it's fine.
    const { desktopCapturer, screen } = await import('electron')
    const { width, height } = screen.getPrimaryDisplay().bounds

    const sources = await desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: { width, height },
    })

    const primary = sources[0]
    if (!primary) {
      console.warn('[devcore-screenshot] No screen source found')
      return -1
    }

    // thumbnail is a NativeImage — convert to base64 PNG
    const png = primary.thumbnail.toPNG()
    const b64 = png.toString('base64')

    sock.send(JSON.stringify({
      type: 'screenshot_frame',
      image_b64: b64,
    }))

    console.log(`[devcore-screenshot] Sent ${Math.round(b64.length / 1024)} KB`)
    return 0  // actual buffer count comes back async via WS message → overlay
  } catch (err) {
    console.error('[devcore-screenshot] Capture failed:', err)
    return -1
  }
}
