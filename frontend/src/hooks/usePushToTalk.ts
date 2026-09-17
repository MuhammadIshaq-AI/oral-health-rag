import { useCallback, useEffect, useRef, useState } from 'react'
import { sttStreamUrl, type SttResult } from '../api'
import { CAPTURE_WORKLET_SOURCE, PcmStreamer } from '../lib/audio'

export type PttStatus = 'idle' | 'starting' | 'recording' | 'finishing' | 'error'

export interface PushToTalkOptions {
  onResult: (result: SttResult) => void
  language?: string
  /** Recording stops automatically after this many seconds. */
  maxSeconds?: number
}

export interface PushToTalkControls {
  status: PttStatus
  partial: string
  error: string | null
  analyser: AnalyserNode | null
  supported: boolean
  start: () => void
  stop: () => void
  cancel: () => void
  clearError: () => void
}

interface Session {
  stream: MediaStream | null
  ctx: AudioContext | null
  source: MediaStreamAudioSourceNode | null
  node: AudioWorkletNode | ScriptProcessorNode | null
  sink: GainNode | null
  ws: WebSocket | null
  streamer: PcmStreamer | null
  queue: (ArrayBuffer | string)[]
  capturing: boolean
  ended: boolean
  done: boolean
  abortStart: boolean
  timers: number[]
}

const FRAME_MS = 200
const FINAL_TIMEOUT_MS = 45_000

function newSession(): Session {
  return {
    stream: null,
    ctx: null,
    source: null,
    node: null,
    sink: null,
    ws: null,
    streamer: null,
    queue: [],
    capturing: false,
    ended: false,
    done: false,
    abortStart: false,
    timers: [],
  }
}

function micErrorMessage(err: unknown): string {
  const name = (err as { name?: string } | null)?.name
  if (name === 'NotAllowedError' || name === 'SecurityError' || name === 'PermissionDeniedError') {
    return 'Microphone access was blocked. To use voice, allow the microphone for this site in your browser settings — or type your question instead.'
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError' || name === 'OverconstrainedError') {
    return 'We could not find a microphone. Please check one is connected, or type your question instead.'
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return 'Your microphone is being used by another app. Close that app and try again, or type your question instead.'
  }
  return 'We could not start the microphone. Please try again, or type your question instead.'
}

function isSttFinal(msg: Record<string, unknown>): boolean {
  return msg.type === 'final' && typeof msg.text === 'string'
}

/**
 * Captures microphone audio, streams 16 kHz Int16 PCM frames to
 * WS /api/stt/stream, surfaces partial transcripts and reports the final result.
 */
export function usePushToTalk({ onResult, language = 'en', maxSeconds = 60 }: PushToTalkOptions): PushToTalkControls {
  const [status, setStatus] = useState<PttStatus>('idle')
  const [partial, setPartial] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null)
  const sessionRef = useRef<Session | null>(null)
  const onResultRef = useRef(onResult)

  useEffect(() => {
    onResultRef.current = onResult
  }, [onResult])

  const supported =
    typeof window !== 'undefined' &&
    typeof navigator !== 'undefined' &&
    Boolean(navigator.mediaDevices?.getUserMedia) &&
    typeof WebSocket !== 'undefined' &&
    (typeof AudioContext !== 'undefined' ||
      typeof (window as unknown as { webkitAudioContext?: unknown }).webkitAudioContext !== 'undefined')

  const releaseAudio = useCallback((s: Session) => {
    s.capturing = false
    if (s.node) {
      if ('port' in s.node) s.node.port.onmessage = null
      else s.node.onaudioprocess = null
      try {
        s.node.disconnect()
      } catch {
        /* already disconnected */
      }
    }
    try {
      s.source?.disconnect()
      s.sink?.disconnect()
    } catch {
      /* already disconnected */
    }
    s.stream?.getTracks().forEach((t) => t.stop())
    if (s.ctx && s.ctx.state !== 'closed') void s.ctx.close().catch(() => undefined)
    s.node = null
    s.source = null
    s.sink = null
    s.stream = null
    s.ctx = null
    setAnalyser(null)
  }, [])

  const teardown = useCallback(
    (s: Session) => {
      s.done = true
      s.timers.forEach((t) => window.clearTimeout(t))
      s.timers = []
      releaseAudio(s)
      const ws = s.ws
      if (ws) {
        ws.onopen = null
        ws.onmessage = null
        ws.onerror = null
        ws.onclose = null
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          try {
            ws.close()
          } catch {
            /* ignore */
          }
        }
      }
      s.ws = null
      if (sessionRef.current === s) sessionRef.current = null
    },
    [releaseAudio],
  )

  const fail = useCallback(
    (s: Session, message: string) => {
      if (s.done) return
      teardown(s)
      setStatus('error')
      setError(message)
    },
    [teardown],
  )

  const send = useCallback((s: Session, data: ArrayBuffer | string) => {
    const ws = s.ws
    if (!ws) return
    if (ws.readyState === WebSocket.OPEN) ws.send(data)
    else if (ws.readyState === WebSocket.CONNECTING) s.queue.push(data)
  }, [])

  const finalize = useCallback(
    (s: Session) => {
      if (s.done || s.ended) return
      s.ended = true
      const rest = s.streamer?.flush()
      releaseAudio(s)
      if (rest) send(s, rest)
      send(s, JSON.stringify({ type: 'end' }))
      setStatus('finishing')
      s.timers.push(
        window.setTimeout(
          () => fail(s, 'Working out what you said took too long. Please try again, or type your question.'),
          FINAL_TIMEOUT_MS,
        ),
      )
    },
    [fail, releaseAudio, send],
  )

  const stop = useCallback(() => {
    const s = sessionRef.current
    if (!s || s.done || s.ended) return
    if (!s.capturing) {
      // Still waiting for microphone permission / setup: abandon this attempt.
      // The pending setup notices `done` and releases anything it acquired.
      s.abortStart = true
      teardown(s)
      setStatus('idle')
      return
    }
    // Ask the worklet to hand over its partial buffer, then finish shortly after.
    if (s.node && 'port' in s.node) s.node.port.postMessage('flush')
    s.timers.push(window.setTimeout(() => finalize(s), 60))
  }, [finalize, teardown])

  const cancel = useCallback(() => {
    const s = sessionRef.current
    if (s) teardown(s)
    setStatus('idle')
    setPartial('')
  }, [teardown])

  const start = useCallback(() => {
    if (sessionRef.current) return
    setError(null)
    setPartial('')
    if (!supported) {
      setStatus('error')
      setError('Voice recording is not available in this browser. You can type your question or upload a recording.')
      return
    }
    const s = newSession()
    sessionRef.current = s
    setStatus('starting')

    const run = async () => {
      let stream: MediaStream
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        })
      } catch (err) {
        if (!s.done) fail(s, micErrorMessage(err))
        return
      }
      s.stream = stream
      if (s.done || s.abortStart) {
        teardown(s)
        return
      }

      const Ctx =
        window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      const ctx = new Ctx()
      s.ctx = ctx
      try {
        if (ctx.state === 'suspended') await ctx.resume()
      } catch {
        /* resume can fail harmlessly on some browsers */
      }
      const source = ctx.createMediaStreamSource(stream)
      const analyserNode = ctx.createAnalyser()
      analyserNode.fftSize = 1024
      source.connect(analyserNode)
      const sink = ctx.createGain()
      sink.gain.value = 0
      sink.connect(ctx.destination)
      s.source = source
      s.sink = sink
      s.streamer = new PcmStreamer(ctx.sampleRate, FRAME_MS)

      const onSamples = (block: Float32Array) => {
        if (!s.streamer || s.ended || s.done) return
        for (const frame of s.streamer.push(block)) send(s, frame)
      }

      let node: AudioWorkletNode | ScriptProcessorNode | null = null
      if (ctx.audioWorklet && typeof AudioWorkletNode !== 'undefined') {
        const url = URL.createObjectURL(new Blob([CAPTURE_WORKLET_SOURCE], { type: 'application/javascript' }))
        try {
          await ctx.audioWorklet.addModule(url)
          const worklet = new AudioWorkletNode(ctx, 'pcm-capture', {
            numberOfInputs: 1,
            numberOfOutputs: 1,
            channelCount: 1,
            channelCountMode: 'explicit',
          })
          worklet.port.onmessage = (e: MessageEvent<Float32Array>) => onSamples(e.data)
          node = worklet
        } catch {
          node = null
        } finally {
          URL.revokeObjectURL(url)
        }
      }
      if (!node) {
        const processor = ctx.createScriptProcessor(4096, 1, 1)
        processor.onaudioprocess = (e) => onSamples(new Float32Array(e.inputBuffer.getChannelData(0)))
        node = processor
      }
      s.node = node
      source.connect(node)
      node.connect(sink)

      if (s.done || s.abortStart) {
        teardown(s)
        return
      }

      let ws: WebSocket
      try {
        ws = new WebSocket(sttStreamUrl())
      } catch {
        fail(s, 'We could not connect to the speech service. Please try again, or type your question.')
        return
      }
      ws.binaryType = 'arraybuffer'
      s.ws = ws
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'start', language }))
        for (const item of s.queue) ws.send(item)
        s.queue = []
      }
      ws.onmessage = (event: MessageEvent) => {
        if (typeof event.data !== 'string') return
        let msg: Record<string, unknown>
        try {
          msg = JSON.parse(event.data) as Record<string, unknown>
        } catch {
          return
        }
        if (msg.type === 'partial' && typeof msg.text === 'string') {
          setPartial(msg.text)
        } else if (isSttFinal(msg)) {
          const result = msg as unknown as SttResult
          teardown(s)
          setStatus('idle')
          setPartial(result.text)
          onResultRef.current(result)
        } else if (msg.type === 'error') {
          const detail = typeof msg.message === 'string' ? ` (${msg.message})` : ''
          fail(s, `The speech service had a problem${detail}. Please try again, or type your question.`)
        }
      }
      ws.onerror = () => {
        fail(s, 'We lost connection to the speech service. Please try again, or type your question.')
      }
      ws.onclose = () => {
        fail(s, 'The speech service closed the connection before we heard back. Please try again.')
      }

      s.capturing = true
      setAnalyser(analyserNode)
      setStatus('recording')
      s.timers.push(window.setTimeout(() => finalize(s), maxSeconds * 1000))
    }

    run().catch(() => {
      fail(s, 'We could not start recording. Please try again, or type your question instead.')
    })
  }, [fail, finalize, language, maxSeconds, send, supported, teardown])

  const clearError = useCallback(() => {
    setError(null)
    setStatus((prev) => (prev === 'error' ? 'idle' : prev))
  }, [])

  useEffect(
    () => () => {
      const s = sessionRef.current
      if (s) teardown(s)
    },
    [teardown],
  )

  return { status, partial, error, analyser, supported, start, stop, cancel, clearError }
}
