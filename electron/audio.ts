import * as naudiodon from 'naudiodon'
import WebSocket from 'ws'
import { getOverlayWindow } from './overlay'

let micInput: naudiodon.IoStreamRead | null = null
let sysInput: naudiodon.IoStreamRead | null = null
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

function _stopStreams() {
  try { micInput?.quit() } catch { /* already stopped */ }
  try { sysInput?.quit() } catch { /* already stopped */ }
  micInput = sysInput = null
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
    try {
      localWs.send(JSON.stringify({ type: 'auth', token }))
      localWs.send(JSON.stringify({
        type: 'session_start',
        session_id: sessionId,
        context: {
          job_title:   (context as any).jobTitle   ?? '',
          company:     (context as any).company    ?? '',
          resume_text: (context as any).resumeText ?? '',
          jd_text:     (context as any).jdText     ?? '',
          files:       (context as any).files      ?? [],
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
    // Don't call stopAudioCapture() here — let 'close' fire and handle reconnect
  })

  localWs.on('close', (code: number) => {
    // Only act if this is still the active socket (guard against stale close events)
    if (ws === localWs) ws = null
    // 1000 = normal closure (user called endSession/pause), 4001 = auth failure — don't reconnect
    const intentional = code === 1000 || code === 4001 || _lastArgs === null
    if (!intentional) {
      console.log(`[devcore-audio] WS closed unexpectedly (code=${code}) — scheduling reconnect`)
      _scheduleReconnect()  // _scheduleReconnect stops streams itself
    } else {
      _stopStreams()
    }
  })

  // Audio device setup — wrapped so a naudiodon failure doesn't kill the WS session.
  try {
    const devices = naudiodon.getDevices()
    const wasapiDevices = devices.filter((d: any) => d.hostAPIName === 'Windows WASAPI')
    console.log('[devcore-audio] All WASAPI devices:')
    wasapiDevices.forEach((d: any) => console.log(`  [${d.id}] "${d.name}" | inputs=${d.maxInputChannels} | loopback=${d.isLoopbackDevice}`))

    // naudiodon on Windows doesn't set isLoopbackDevice reliably — detect by name pattern
    const isLoopbackDevice = (d: any) =>
      d.isLoopbackDevice === true ||
      (d.maxInputChannels > 0 && /loopback|stereo mix|what u hear|wave out|\[loopback\]/i.test(d.name))

    const loopback = devices.find((d: any) =>
      d.hostAPIName === 'Windows WASAPI' && isLoopbackDevice(d)
    )
    const mic = devices.find((d: any) =>
      d.hostAPIName === 'Windows WASAPI' &&
      d.maxInputChannels > 0 &&
      !isLoopbackDevice(d)
    )
    console.log(`[devcore-audio] Selected mic: [${micDeviceId ?? mic?.id}] "${mic?.name}" | loopback: [${sysDeviceId ?? loopback?.id}] "${loopback?.name ?? 'none found'}"`)

    const TARGET_RATE     = 16000
    const CANDIDATE_RATES = [48000, 44100, 16000]

    // VAD parameters
    const FRAME_MS             = 30      // RMS measured per this window
    const SPEECH_RMS_THRESHOLD = 0.004  // above = speech
    const SILENCE_FRAMES_FLUSH = 20     // ~600ms pause → flush utterance
    const MIN_SPEECH_BYTES     = TARGET_RATE * 0.2 * 2  // 200ms minimum utterance
    const MIC_GAIN             = 4.0    // software boost for quiet headset mics

    function resampleTo16k(buf: Buffer, fromRate: number): Buffer {
      if (fromRate === TARGET_RATE) return buf
      const ratio = fromRate / TARGET_RATE
      const inSamples = buf.length / 2
      const outSamples = Math.floor(inSamples / ratio)
      const out = Buffer.alloc(outSamples * 2)
      for (let i = 0; i < outSamples; i++) {
        const srcIdx = Math.min(Math.round(i * ratio), inSamples - 1)
        out.writeInt16LE(buf.readInt16LE(srcIdx * 2), i * 2)
      }
      return out
    }

    function stereoToMono(buf: Buffer): Buffer {
      const frames = Math.floor(buf.length / 4)
      const out = Buffer.alloc(frames * 2)
      for (let i = 0; i < frames; i++) {
        const l = buf.readInt16LE(i * 4)
        const r = buf.readInt16LE(i * 4 + 2)
        out.writeInt16LE(Math.round((l + r) / 2), i * 2)
      }
      return out
    }

    function applyGain(buf: Buffer, gain: number): Buffer {
      const out = Buffer.alloc(buf.length)
      for (let i = 0; i < buf.length; i += 2) {
        const s = Math.max(-32768, Math.min(32767, Math.round(buf.readInt16LE(i) * gain)))
        out.writeInt16LE(s, i)
      }
      return out
    }

    function frameRms(buf: Buffer): number {
      const samples = buf.length / 2
      if (samples === 0) return 0
      let sumSq = 0
      for (let i = 0; i < samples; i++) {
        const s = buf.readInt16LE(i * 2) / 32768.0
        sumSq += s * s
      }
      return Math.sqrt(sumSq / samples)
    }

    function sendChunk(pcm: Buffer, streamId: 0x01 | 0x02) {
      const sock = ws
      if (!sock || sock.readyState !== 1) return
      const seq = chunkSeq++ % 65536
      const header = Buffer.alloc(3)
      header.writeUInt8(streamId, 0)
      header.writeUInt16BE(seq, 1)
      try { sock.send(Buffer.concat([header, pcm])) } catch { /* socket closed mid-send */ }
    }

    function startStream(deviceId: number, streamId: 0x01 | 0x02): naudiodon.IoStreamRead | null {
      const deviceInfo = naudiodon.getDevices().find((d: any) => d.id === deviceId) as any
      const maxCh: number = deviceInfo?.maxInputChannels ?? 2
      const CHANNELS = maxCh >= 2 ? 2 : 1
      const isMic = streamId === 0x01
      const gain  = isMic ? MIC_GAIN : 1.0

      for (const captureRate of CANDIDATE_RATES) {
        try {
          // VAD state per stream
          let rawBuf       = Buffer.alloc(0)
          let speechBuf    = Buffer.alloc(0)  // accumulated 16kHz mono speech
          let silentFrames = 0
          let inSpeech     = false

          const FRAME_SAMPLES_RAW = Math.floor((captureRate * FRAME_MS) / 1000)
          const FRAME_BYTES_RAW   = FRAME_SAMPLES_RAW * CHANNELS * 2

          const input = naudiodon.AudioIO({
            inOptions: {
              deviceId,
              channelCount: CHANNELS,
              sampleRate: captureRate,
              framesPerBuffer: 4096,
              sampleFormat: naudiodon.SampleFormat16Bit,
            }
          })

          input.on('data', (chunk: Buffer) => {
            if (!ws || ws.readyState !== 1) {
              rawBuf = speechBuf = Buffer.alloc(0)
              silentFrames = 0; inSpeech = false
              return
            }
            rawBuf = Buffer.concat([rawBuf, chunk])

            // Process complete 30ms frames
            while (rawBuf.length >= FRAME_BYTES_RAW) {
              const frame = rawBuf.subarray(0, FRAME_BYTES_RAW)
              rawBuf = rawBuf.subarray(FRAME_BYTES_RAW)

              const mono      = CHANNELS === 2 ? stereoToMono(frame) : Buffer.from(frame)
              const resampled = resampleTo16k(mono, captureRate)
              const boosted   = gain !== 1.0 ? applyGain(resampled, gain) : resampled
              const rms       = frameRms(boosted)

              if (rms >= SPEECH_RMS_THRESHOLD) {
                speechBuf    = Buffer.concat([speechBuf, boosted])
                silentFrames = 0
                inSpeech     = true
              } else if (inSpeech) {
                // Include trailing silence frames for natural speech boundaries
                speechBuf    = Buffer.concat([speechBuf, boosted])
                silentFrames++
                if (silentFrames >= SILENCE_FRAMES_FLUSH) {
                  // Pause detected — send utterance if long enough
                  if (speechBuf.length >= MIN_SPEECH_BYTES) {
                    sendChunk(speechBuf, streamId)
                  }
                  speechBuf    = Buffer.alloc(0)
                  silentFrames = 0
                  inSpeech     = false
                }
              }
            }
          })

          input.on('error', (err: Error) => {
            console.error('[devcore-audio] stream error:', err.message)
          })
          input.start()
          console.log(`[devcore-audio] Device ${deviceId} (${isMic ? 'mic' : 'system'}) VAD started @ ${captureRate} Hz gain=${gain}`)
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
      if (sysId != null) sysInput = startStream(sysId, 0x02)
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
