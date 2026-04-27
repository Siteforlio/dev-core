import * as naudiodon from 'naudiodon'
import WebSocket from 'ws'

let micInput: naudiodon.IoStreamRead | null = null
let sysInput: naudiodon.IoStreamRead | null = null
let ws: WebSocket | null = null
let chunkSeq = 0

export function startAudioCapture(wsUrl: string, token: string, audioSource: 'mic' | 'system' | 'both') {
  ws = new WebSocket(wsUrl)
  ws.on('open', () => {
    ws!.send(JSON.stringify({ type: 'auth', token }))
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
      buf = Buffer.concat([buf, chunk])
      while (buf.length >= CHUNK_BYTES) {
        sendChunk(buf.slice(0, CHUNK_BYTES), streamId)
        buf = buf.slice(CHUNK_BYTES)
      }
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
}

export function getActiveWs() { return ws }
