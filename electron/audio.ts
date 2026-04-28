import * as naudiodon from 'naudiodon'
import WebSocket from 'ws'

let micInput: naudiodon.IoStreamRead | null = null
let sysInput: naudiodon.IoStreamRead | null = null
let ws: WebSocket | null = null
let chunkSeq = 0

export function startAudioCapture(wsUrl: string, token: string, audioSource: 'mic' | 'system' | 'both') {
  stopAudioCapture()   // no-op if nothing running; prevents orphaned streams on double-start
  ws = new WebSocket(wsUrl)
  ws.on('open', () => {
    ws!.send(JSON.stringify({ type: 'auth', token }))
  })
  ws.on('error', (err: Error) => {
    console.error('[audio] WS error:', err.message)
    stopAudioCapture()
  })
  ws.on('close', () => {
    micInput = sysInput = null   // streams already stopped by device; don't double-quit
    ws = null
  })

  const devices = naudiodon.getDevices()
  // isLoopbackDevice is a WASAPI-specific field not in the base typings — cast to any
  const loopback = devices.find((d: any) => d.hostAPIName === 'Windows WASAPI' && d.isLoopbackDevice)
  const mic = devices.find((d: any) => d.hostAPIName === 'Windows WASAPI' && d.maxInputChannels > 0 && !d.isLoopbackDevice)

  const CHUNK_MS = 2000
  const SAMPLE_RATE = 16000
  const CHUNK_SAMPLES = (SAMPLE_RATE * CHUNK_MS) / 1000
  const CHUNK_BYTES = CHUNK_SAMPLES * 2  // PCM16 = 2 bytes/sample

  function sendChunk(pcm: Buffer, streamId: 0x01 | 0x02) {
    if (!ws || ws.readyState !== 1 /* WebSocket.OPEN */) return
    const seq = chunkSeq++ % 65536
    const header = Buffer.alloc(3)
    header.writeUInt8(streamId, 0)
    header.writeUInt16BE(seq, 1)
    ws.send(Buffer.concat([header, pcm]))
  }

  function startStream(deviceId: number, streamId: 0x01 | 0x02): naudiodon.IoStreamRead {
    let buf = Buffer.alloc(0)
    const input = naudiodon.AudioIO({
      inOptions: {
        deviceId,
        channelCount: 1,
        sampleRate: SAMPLE_RATE,
        framesPerBuffer: 4096,
        sampleFormat: naudiodon.SampleFormat16Bit,
      }
    })
    input.on('data', (chunk: Buffer) => {
      if (!ws || ws.readyState !== 1) {
        buf = Buffer.alloc(0)   // discard; WS not open
        return
      }
      buf = Buffer.concat([buf, chunk])
      while (buf.length >= CHUNK_BYTES) {
        sendChunk(buf.subarray(0, CHUNK_BYTES), streamId)
        buf = buf.subarray(CHUNK_BYTES)
      }
    })
    input.on('error', (err: Error) => {
      console.error('[audio] stream error:', err.message)
      stopAudioCapture()
    })
    input.start()
    return input
  }

  if ((audioSource === 'system' || audioSource === 'both') && loopback) {
    sysInput = startStream(loopback.id, 0x02)
  }
  if ((audioSource === 'mic' || audioSource === 'both') && mic) {
    micInput = startStream(mic.id, 0x01)
  }
}

export function stopAudioCapture() {
  micInput?.quit()
  sysInput?.quit()
  ws?.close()
  micInput = sysInput = ws = null
  chunkSeq = 0
}

export function getActiveWs() { return ws }
