/**
 * audio-worker.ts — runs in a worker_threads Worker.
 *
 * Handles all CPU-intensive audio processing off the main thread:
 *   - stereo → mono downmix
 *   - nearest-neighbour resample to 16 kHz
 *   - software gain
 *   - RMS calculation (VAD energy detection)
 *   - VAD state machine (accumulate speech, flush on silence)
 *
 * Protocol (MessageChannel / parentPort):
 *   Main → Worker  { type: "init", channels, captureRate, gain, streamId, isMic }
 *   Main → Worker  { type: "frame", buf: ArrayBuffer }   (transferable)
 *   Worker → Main  { type: "audio_level", rms }          (isMic streams only)
 *   Worker → Main  { type: "speech_chunk", buf: ArrayBuffer, streamId }  (transferable)
 */
import { parentPort } from 'worker_threads'

if (!parentPort) throw new Error('audio-worker must run inside a Worker')

const TARGET_RATE          = 16000
const FRAME_MS             = 30
const SPEECH_RMS_THRESHOLD = 0.004
const SILENCE_FRAMES_FLUSH = 10          // ~300 ms of silence → flush
const MIN_SPEECH_BYTES     = TARGET_RATE * 0.15 * 2   // 150 ms minimum utterance
const MAX_SPEECH_BYTES     = TARGET_RATE * 8 * 2      // 8 s max — force flush

// Config (set once via "init" message)
let channels    = 1
let captureRate = 16000
let gain        = 1.0
let streamId    = 0x01
let isMic       = false

// VAD state
let rawBuf       = Buffer.alloc(0)
let speechBuf    = Buffer.alloc(0)
let silentFrames = 0
let inSpeech     = false

let frameBytes = 0  // calculated after init

// ── DSP helpers ──────────────────────────────────────────────────────────────

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

function applyGain(buf: Buffer, g: number): Buffer {
  const out = Buffer.alloc(buf.length)
  for (let i = 0; i < buf.length; i += 2) {
    const s = Math.max(-32768, Math.min(32767, Math.round(buf.readInt16LE(i) * g)))
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

// ── Message handler ──────────────────────────────────────────────────────────

parentPort.on('message', (msg: { type: string; channels?: number; captureRate?: number; gain?: number; streamId?: number; isMic?: boolean; buf?: ArrayBuffer }) => {
  if (msg.type === 'init') {
    channels    = msg.channels    ?? 1
    captureRate = msg.captureRate ?? 16000
    gain        = msg.gain        ?? 1.0
    streamId    = msg.streamId    ?? 0x01
    isMic       = msg.isMic       ?? false
    frameBytes  = Math.floor((captureRate * FRAME_MS) / 1000) * channels * 2
    // Reset VAD state on (re)init
    rawBuf = speechBuf = Buffer.alloc(0)
    silentFrames = 0
    inSpeech = false
    return
  }

  if (msg.type === 'frame' && msg.buf) {
    const chunk = Buffer.from(msg.buf)
    rawBuf = Buffer.concat([rawBuf, chunk])

    while (rawBuf.length >= frameBytes) {
      const frame = rawBuf.subarray(0, frameBytes)
      rawBuf = rawBuf.subarray(frameBytes)

      const mono      = channels === 2 ? stereoToMono(Buffer.from(frame)) : Buffer.from(frame)
      const resampled = resampleTo16k(mono, captureRate)
      const boosted   = gain !== 1.0 ? applyGain(resampled, gain) : resampled
      const rms       = frameRms(boosted)

      // Send waveform level (mic only)
      if (isMic) {
        parentPort!.postMessage({ type: 'audio_level', rms })
      }

      if (rms >= SPEECH_RMS_THRESHOLD) {
        speechBuf    = Buffer.concat([speechBuf, boosted])
        silentFrames = 0
        inSpeech     = true
        // Force flush if utterance exceeds max duration
        if (speechBuf.length >= MAX_SPEECH_BYTES) {
          const ab = speechBuf.buffer.slice(speechBuf.byteOffset, speechBuf.byteOffset + speechBuf.byteLength)
          parentPort!.postMessage({ type: 'speech_chunk', buf: ab, streamId }, [ab as ArrayBuffer])
          speechBuf = Buffer.alloc(0)
          inSpeech  = false
        }
      } else if (inSpeech) {
        speechBuf    = Buffer.concat([speechBuf, boosted])
        silentFrames++
        if (silentFrames >= SILENCE_FRAMES_FLUSH) {
          if (speechBuf.length >= MIN_SPEECH_BYTES) {
            const ab = speechBuf.buffer.slice(speechBuf.byteOffset, speechBuf.byteOffset + speechBuf.byteLength)
            parentPort!.postMessage({ type: 'speech_chunk', buf: ab, streamId }, [ab as ArrayBuffer])
          }
          speechBuf    = Buffer.alloc(0)
          silentFrames = 0
          inSpeech     = false
        }
      }
    }
  }
})
