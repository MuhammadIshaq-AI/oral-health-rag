import { describe, expect, it } from 'vitest'
import { PcmStreamer, downsample, floatTo16BitPCM } from './audio'

describe('downsample', () => {
  it('reduces 48 kHz to 16 kHz by averaging', () => {
    const input = new Float32Array([0.3, 0.3, 0.3, -0.6, -0.6, -0.6, 1])
    const { output, consumed } = downsample(input, 48_000, 16_000)
    expect(Array.from(output).map((v) => Number(v.toFixed(3)))).toEqual([0.3, -0.6])
    expect(consumed).toBe(6)
  })

  it('handles non-integer ratios', () => {
    const input = new Float32Array(44_100).fill(0.5)
    const { output } = downsample(input, 44_100, 16_000)
    expect(output.length).toBe(16_000)
    expect(output.every((v) => Math.abs(v - 0.5) < 1e-6)).toBe(true)
  })

  it('passes through equal rates', () => {
    const input = new Float32Array([0.1, 0.2])
    expect(downsample(input, 16_000, 16_000).output).toEqual(input)
  })
})

describe('floatTo16BitPCM', () => {
  it('writes clamped little-endian int16', () => {
    const view = new DataView(floatTo16BitPCM(new Float32Array([0, 1, -1, 2])))
    expect(view.getInt16(0, true)).toBe(0)
    expect(view.getInt16(2, true)).toBe(32767)
    expect(view.getInt16(4, true)).toBe(-32768)
    expect(view.getInt16(6, true)).toBe(32767)
  })
})

describe('PcmStreamer', () => {
  it('emits ~200 ms frames at 16 kHz', () => {
    const streamer = new PcmStreamer(48_000, 200)
    const frames = streamer.push(new Float32Array(48_000))
    expect(frames).toHaveLength(5)
    expect(frames[0].byteLength).toBe(3200 * 2)
    expect(streamer.flush()).toBeNull()
  })

  it('flushes the remainder', () => {
    const streamer = new PcmStreamer(48_000, 200)
    streamer.push(new Float32Array(1_000))
    expect(streamer.flush()?.byteLength).toBe(333 * 2)
  })
})
