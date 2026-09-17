import { Loader2, Mic, Square } from 'lucide-react'
import { useRef, type KeyboardEvent, type MouseEvent, type PointerEvent } from 'react'
import type { PttStatus } from '../hooks/usePushToTalk'

interface PushToTalkProps {
  status: PttStatus
  disabled?: boolean
  onStart: () => void
  onStop: () => void
}

/** Holding longer than this counts as press-and-hold; shorter presses toggle. */
const HOLD_THRESHOLD_MS = 450

/**
 * Large round microphone button.
 * - Press and hold (mouse or touch): records while held, stops on release.
 * - Quick tap / click: starts recording; tap again to stop.
 * - Keyboard (Space / Enter): toggles recording.
 */
export function PushToTalk({ status, disabled, onStart, onStop }: PushToTalkProps) {
  const pressRef = useRef<{ startedHere: boolean; downAt: number } | null>(null)
  const busy = status === 'finishing'
  const active = status === 'recording' || status === 'starting'

  const onPointerDown = (e: PointerEvent<HTMLButtonElement>) => {
    if (disabled || busy) return
    if (e.pointerType === 'mouse' && e.button !== 0) return
    e.preventDefault()
    try {
      e.currentTarget.setPointerCapture(e.pointerId)
    } catch {
      /* not supported */
    }
    e.currentTarget.focus({ preventScroll: true })
    if (active) {
      // Second tap in toggle mode stops.
      pressRef.current = null
      onStop()
      return
    }
    pressRef.current = { startedHere: true, downAt: performance.now() }
    onStart()
  }

  const endPress = () => {
    const press = pressRef.current
    pressRef.current = null
    if (!press?.startedHere) return
    const held = performance.now() - press.downAt
    // Only a genuine hold stops on release; a short tap leaves recording on (toggle mode).
    if (held >= HOLD_THRESHOLD_MS && status === 'recording') onStop()
  }

  const onClick = (e: MouseEvent<HTMLButtonElement>) => {
    // Pointer interactions are handled above; `detail === 0` means keyboard activation.
    if (e.detail !== 0 || disabled || busy) return
    if (active) onStop()
    else onStart()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if ((e.key === ' ' || e.key === 'Enter') && e.repeat) e.preventDefault()
  }

  const label = busy
    ? 'Working out what you said'
    : active
      ? 'Stop recording'
      : 'Speak your question. Hold to talk, or tap to start and tap again to stop'

  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      disabled={disabled || busy}
      onPointerDown={onPointerDown}
      onPointerUp={endPress}
      onPointerCancel={endPress}
      onClick={onClick}
      onKeyDown={onKeyDown}
      onContextMenu={(e) => e.preventDefault()}
      className={[
        'no-touch-callout relative inline-flex h-[4.5rem] w-[4.5rem] min-h-[72px] min-w-[72px] shrink-0 items-center justify-center rounded-full shadow-md transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-60',
        active
          ? 'bg-red-700 text-white hover:bg-red-800 dark:bg-red-600 dark:hover:bg-red-500'
          : 'bg-teal-700 text-white hover:bg-teal-800 dark:bg-teal-300 dark:text-slate-950 dark:hover:bg-teal-200',
      ].join(' ')}
    >
      {active ? (
        <span
          aria-hidden="true"
          className="absolute inset-0 rounded-full ring-4 ring-red-400/60 motion-safe:animate-pulse"
        />
      ) : null}
      {busy ? (
        <Loader2 aria-hidden="true" className="h-9 w-9 motion-safe:animate-spin" />
      ) : active ? (
        <Square aria-hidden="true" className="h-8 w-8" fill="currentColor" />
      ) : (
        <Mic aria-hidden="true" className="h-9 w-9" />
      )}
    </button>
  )
}
