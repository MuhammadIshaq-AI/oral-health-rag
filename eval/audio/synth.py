"""Synthesise a proxy speech test set with several Piper voices and acoustic conditions.

This is a *proxy* for speech robustness: synthetic voices are cleaner and more
regular than real people. Real accented recordings (e.g. Aboriginal English,
Vietnamese-, Mandarin- and Arabic-accented English, older speakers) must be
collected separately under ethics approval and added to `eval/audio/recorded/`
with the same manifest format (see eval/audio/README.md).

Output: eval/audio/generated/<voice>/<condition>/<question_id>.wav (16 kHz mono)
plus eval/audio/generated/manifest.jsonl.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import wave
from pathlib import Path

import numpy as np

from app.config import ROOT, enable_system_tls, get_settings
from eval.common import gold_questions

OUT_DIR = ROOT / "eval" / "audio" / "generated"
SR = 16_000

#: Piper has no Australian-English voices; these span British regional and US accents.
VOICES = (
    "en_GB-alba-medium",  # Scottish English, female
    "en_GB-northern_english_male-medium",  # Northern English, male
    "en_GB-southern_english_female-low",  # Southern English, female, low quality
    "en_US-lessac-medium",  # General American, female
)
CONDITIONS = ("clean", "noise_snr10", "telephone", "slow")


def _to_float(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(wav_bytes)) as w:
        sr = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    return pcm, sr


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Linear-interpolation resampling (adequate for a robustness proxy)."""
    if sr_in == sr_out:
        return x
    n_out = round(len(x) * sr_out / sr_in)
    return np.interp(np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x).astype(np.float32)


def add_noise(x: np.ndarray, snr_db: float, seed: int) -> np.ndarray:
    """Additive white Gaussian noise at a target SNR (deterministic seed)."""
    rng = np.random.default_rng(seed)
    power = float(np.mean(x**2)) or 1e-8
    noise = rng.normal(0.0, np.sqrt(power / (10 ** (snr_db / 10))), size=x.shape)
    return np.clip(x + noise, -1, 1).astype(np.float32)


def telephone(x: np.ndarray, sr: int) -> np.ndarray:
    """300–3400 Hz band-pass via FFT mask, down to 8 kHz and back (narrowband phone line)."""
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    spec[(freqs < 300) | (freqs > 3400)] = 0
    band = np.fft.irfft(spec, n=len(x)).astype(np.float32)
    return resample(resample(band, sr, 8000), 8000, sr)


def write_wav(path: Path, x: np.ndarray, sr: int = SR) -> None:
    """16-bit mono WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def synthesise(voices: tuple[str, ...] = VOICES, include_todo: bool = False) -> Path:
    """Generate the audio set and manifest; returns the manifest path."""
    from app.tts.piper import PiperTTS

    enable_system_tls()
    settings = get_settings()
    questions = gold_questions(include_todo=include_todo)
    rows = []
    for v_idx, voice in enumerate(voices):
        try:
            tts = PiperTTS(voice, settings.models_dir)
        except Exception as exc:
            logging.warning("Skipping voice %s: %s", voice, exc)
            continue
        for q_idx, q in enumerate(questions):
            for cond in CONDITIONS:
                wav_bytes = tts.synthesize(
                    q["question"], length_scale=1.35 if cond == "slow" else None
                )
                x, sr = _to_float(wav_bytes)
                x = resample(x, sr, SR)
                if cond == "noise_snr10":
                    x = add_noise(x, 10.0, seed=1000 * v_idx + q_idx)
                elif cond == "telephone":
                    x = telephone(x, SR)
                path = OUT_DIR / voice / cond / f"{q['id']}.wav"
                write_wav(path, x)
                rows.append(
                    {
                        "id": f"{voice}/{cond}/{q['id']}",
                        "question_id": q["id"],
                        "voice": voice,
                        "condition": cond,
                        "source": "piper-synthetic",
                        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "reference": q["question"],
                    }
                )
    manifest = OUT_DIR / "manifest.jsonl"
    manifest.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    """CLI."""
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="Synthesise the proxy speech test set")
    ap.add_argument("--voices", default=",".join(VOICES))
    args = ap.parse_args()
    path = synthesise(tuple(args.voices.split(",")))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
