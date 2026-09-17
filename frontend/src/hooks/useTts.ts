import { useCallback, useEffect, useRef, useState } from 'react'
import { synthesize } from '../api'

export interface TtsControls {
  /** False once the backend has shown TTS is unavailable. */
  available: boolean
  /** Id of the message currently being fetched or played. */
  activeId: string | null
  status: 'idle' | 'loading' | 'playing'
  speak: (id: string, text: string) => void
  stop: () => void
}

/**
 * Plays server-side text-to-speech (POST /api/tts → audio/wav) through an
 * Audio element fed by a blob URL.
 */
export function useTts(enabled: boolean): TtsControls {
  const [failed, setFailed] = useState(false)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [status, setStatus] = useState<TtsControls['status']>('idle')
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const urlRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const cleanup = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    const audio = audioRef.current
    if (audio) {
      audio.onended = null
      audio.onerror = null
      audio.pause()
      audio.removeAttribute('src')
      audio.load()
    }
    audioRef.current = null
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
    }
  }, [])

  const stop = useCallback(() => {
    cleanup()
    setActiveId(null)
    setStatus('idle')
  }, [cleanup])

  const speak = useCallback(
    (id: string, text: string) => {
      cleanup()
      const trimmed = text.trim()
      if (!trimmed) return
      const controller = new AbortController()
      abortRef.current = controller
      setActiveId(id)
      setStatus('loading')
      synthesize(trimmed.slice(0, 5000), controller.signal)
        .then((blob) => {
          if (controller.signal.aborted) return
          const url = URL.createObjectURL(blob)
          urlRef.current = url
          const audio = new Audio(url)
          audioRef.current = audio
          audio.onended = () => stop()
          audio.onerror = () => stop()
          setStatus('playing')
          return audio.play().catch(() => {
            // Autoplay blocked or decode error: leave the Listen button usable.
            stop()
          })
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return
          const status = (err as { status?: number }).status
          // 404/501/503 (or unreachable) mean TTS is switched off: hide the controls.
          if (status === undefined || status === 0 || status === 404 || status === 501 || status === 503) {
            setFailed(true)
          }
          stop()
        })
    },
    [cleanup, stop],
  )

  useEffect(() => cleanup, [cleanup])

  return { available: enabled && !failed, activeId, status, speak, stop }
}
