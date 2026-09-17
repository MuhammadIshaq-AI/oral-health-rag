/** Audio helpers for streaming speech to the backend as 16 kHz Int16 PCM. */

export const TARGET_SAMPLE_RATE = 16_000

export interface DownsampleResult {
  /** Downsampled samples at the output rate. */
  output: Float32Array
  /** Number of input samples consumed; the rest should be carried over. */
  consumed: number
}

/**
 * Downsample `input` from `inRate` to `outRate` by averaging each output
 * sample's input window (a simple box low-pass filter which is adequate for
 * speech). Only whole output samples are produced; callers streaming audio
 * should keep `input.subarray(consumed)` and prepend it to the next block.
 */
export function downsample(input: Float32Array, inRate: number, outRate = TARGET_SAMPLE_RATE): DownsampleResult {
  if (outRate <= 0 || inRate <= 0) throw new Error('Sample rates must be positive')
  if (inRate === outRate) return { output: input.slice(), consumed: input.length }
  if (outRate > inRate) throw new Error('Upsampling is not supported')

  const ratio = inRate / outRate
  const outLength = Math.floor(input.length / ratio)
  const output = new Float32Array(outLength)
  for (let i = 0; i < outLength; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(input.length, Math.max(start + 1, Math.floor((i + 1) * ratio)))
    let sum = 0
    for (let j = start; j < end; j++) sum += input[j]
    output[i] = sum / (end - start)
  }
  return { output, consumed: Math.min(input.length, Math.floor(outLength * ratio)) }
}

/** Convert [-1, 1] float samples to little-endian signed 16-bit PCM bytes. */
export function floatTo16BitPCM(input: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(input.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]))
    view.setInt16(i * 2, s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff), true)
  }
  return buffer
}

export function concatFloat32(a: Float32Array, b: Float32Array): Float32Array {
  if (a.length === 0) return b
  if (b.length === 0) return a
  const out = new Float32Array(a.length + b.length)
  out.set(a, 0)
  out.set(b, a.length)
  return out
}

/**
 * Stateful streaming converter: push float blocks at the capture rate, get
 * back Int16 PCM frames of roughly `frameMs` at 16 kHz.
 */
export class PcmStreamer {
  private pending: Float32Array = new Float32Array(0)
  private readonly inRate: number
  private readonly frameInputSamples: number

  constructor(inRate: number, frameMs = 200) {
    this.inRate = inRate
    this.frameInputSamples = Math.max(1, Math.round((inRate * frameMs) / 1000))
  }

  /** Add samples; returns zero or more ready PCM frames. */
  push(block: Float32Array): ArrayBuffer[] {
    this.pending = concatFloat32(this.pending, block)
    const frames: ArrayBuffer[] = []
    while (this.pending.length >= this.frameInputSamples) {
      const chunk = this.pending.subarray(0, this.frameInputSamples)
      const { output, consumed } = downsample(chunk, this.inRate)
      frames.push(floatTo16BitPCM(output))
      this.pending = this.pending.slice(consumed)
    }
    return frames
  }

  /** Convert whatever is left (may be a short final frame). */
  flush(): ArrayBuffer | null {
    if (this.pending.length === 0) return null
    const { output } = downsample(this.pending, this.inRate)
    this.pending = new Float32Array(0)
    return output.length ? floatTo16BitPCM(output) : null
  }
}

/** AudioWorklet processor source, loaded from a Blob URL (no extra file to serve). */
export const CAPTURE_WORKLET_SOURCE = `
class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(2048);
    this.length = 0;
    this.port.onmessage = (event) => {
      if (event.data === 'flush') this.flush();
    };
  }
  flush() {
    if (this.length > 0) {
      this.port.postMessage(this.buffer.slice(0, this.length));
      this.length = 0;
    }
  }
  process(inputs) {
    const input = inputs[0];
    if (input && input[0]) {
      const channel = input[0];
      for (let i = 0; i < channel.length; i++) {
        this.buffer[this.length++] = channel[i];
        if (this.length === this.buffer.length) this.flush();
      }
    }
    return true;
  }
}
registerProcessor('pcm-capture', PcmCaptureProcessor);
`
