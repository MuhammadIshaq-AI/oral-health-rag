import { useEffect, useRef } from 'react'

interface WaveformProps {
  analyser: AnalyserNode | null
  className?: string
}

/** Live microphone waveform drawn from an AnalyserNode. Decorative (aria-hidden). */
export function Waveform({ analyser, className }: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const resize = () => {
      const dpr = window.devicePixelRatio || 1
      const rect = canvas.getBoundingClientRect()
      canvas.width = Math.max(1, Math.round(rect.width * dpr))
      canvas.height = Math.max(1, Math.round(rect.height * dpr))
    }
    resize()
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null
    observer?.observe(canvas)

    const data = analyser ? new Uint8Array(analyser.fftSize) : null
    let raf = 0

    const draw = () => {
      const { width, height } = canvas
      const color = getComputedStyle(canvas).color || '#0f766e'
      ctx.clearRect(0, 0, width, height)
      ctx.lineWidth = Math.max(2, (window.devicePixelRatio || 1) * 2.5)
      ctx.lineJoin = 'round'
      ctx.lineCap = 'round'
      ctx.strokeStyle = color
      ctx.beginPath()
      if (analyser && data) {
        analyser.getByteTimeDomainData(data)
        const step = width / (data.length - 1)
        for (let i = 0; i < data.length; i++) {
          // Exaggerate quiet speech a little so users can see they are being heard.
          const v = (data[i] - 128) / 128
          const y = height / 2 + Math.max(-1, Math.min(1, v * 2.5)) * (height / 2 - ctx.lineWidth)
          if (i === 0) ctx.moveTo(0, y)
          else ctx.lineTo(i * step, y)
        }
      } else {
        ctx.moveTo(0, height / 2)
        ctx.lineTo(width, height / 2)
      }
      ctx.stroke()
      if (analyser) raf = window.requestAnimationFrame(draw)
    }
    draw()

    return () => {
      window.cancelAnimationFrame(raf)
      observer?.disconnect()
    }
  }, [analyser])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={['block h-14 w-full text-teal-700 dark:text-teal-300', className ?? ''].join(' ')}
    />
  )
}
