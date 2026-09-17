"""Local speech-to-text with faster-whisper (no cloud STT)."""

from __future__ import annotations

import io
import math
import threading
from dataclasses import asdict, dataclass, field
from functools import lru_cache

import numpy as np

from app.config import get_settings, resolve_device
from app.llm.base import Timer

SAMPLE_RATE = 16_000

#: Bias decoding towards Australian oral-health vocabulary (improves rare-term accuracy).
INITIAL_PROMPT = (
    "A person in Australia asking about teeth, gums, dentures, wisdom teeth, dry mouth, "
    "a dentist, healthdirect, Medicare or the Child Dental Benefits Schedule."
)


@dataclass
class Segment:
    """One decoded segment."""

    start: float
    end: float
    text: str
    avg_logprob: float
    no_speech_prob: float
    confidence: float


@dataclass
class Transcript:
    """Full transcription result."""

    text: str
    language: str
    language_probability: float
    duration_s: float
    confidence: float
    segments: list[Segment] = field(default_factory=list)
    model: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, object]:
        """JSON-serialisable form."""
        return asdict(self)


def segment_confidence(avg_logprob: float, no_speech_prob: float) -> float:
    """Heuristic per-segment confidence in [0, 1]: exp(mean token log-prob) × P(speech)."""
    return max(0.0, min(1.0, math.exp(avg_logprob) * (1.0 - no_speech_prob)))


def aggregate_confidence(segments: list[Segment]) -> float:
    """Duration-weighted mean segment confidence."""
    total = sum(max(s.end - s.start, 1e-3) for s in segments)
    if not segments or total <= 0:
        return 0.0
    return sum(s.confidence * max(s.end - s.start, 1e-3) for s in segments) / total


def _expose_torch_cuda_libs() -> None:
    """On Windows, let CTranslate2 find the cuBLAS/cuDNN DLLs bundled with the torch wheel."""
    import os
    import sys

    if sys.platform != "win32":
        return
    try:
        import torch

        lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.isdir(lib):
            os.add_dll_directory(lib)
            os.environ["PATH"] = lib + os.pathsep + os.environ.get("PATH", "")
    except ImportError:
        pass


class WhisperSTT:
    """Thread-safe wrapper around a faster-whisper model."""

    def __init__(
        self, model_name: str = "small", device: str = "auto", compute_type: str = "auto"
    ) -> None:
        dev = resolve_device(device)
        if dev == "cuda":
            _expose_torch_cuda_libs()
        from faster_whisper import WhisperModel

        self.model_name = model_name
        if compute_type == "auto":
            compute_type = "int8_float16" if dev == "cuda" else "int8"
        try:
            self.model = WhisperModel(model_name, device=dev, compute_type=compute_type)
            self.device = dev
        except (RuntimeError, ValueError):
            if dev != "cuda":
                raise
            # Missing cuBLAS/cuDNN for CTranslate2: degrade gracefully to CPU.
            self.model = WhisperModel(model_name, device="cpu", compute_type="int8")
            self.device = "cpu"
        self._lock = threading.Lock()

    def transcribe_array(
        self, audio: np.ndarray, language: str | None = None, beam_size: int = 5
    ) -> Transcript:
        """Transcribe mono float32 PCM at 16 kHz."""
        with Timer() as t, self._lock:
            segments_iter, info = self.model.transcribe(
                audio,
                language=language,
                beam_size=beam_size,
                vad_filter=True,
                initial_prompt=INITIAL_PROMPT,
                condition_on_previous_text=False,
            )
            segments = [
                Segment(
                    start=round(s.start, 2),
                    end=round(s.end, 2),
                    text=s.text.strip(),
                    avg_logprob=round(s.avg_logprob, 4),
                    no_speech_prob=round(s.no_speech_prob, 4),
                    confidence=round(segment_confidence(s.avg_logprob, s.no_speech_prob), 4),
                )
                for s in segments_iter
            ]
        return Transcript(
            text=" ".join(s.text for s in segments).strip(),
            language=info.language,
            language_probability=round(float(info.language_probability), 4),
            duration_s=round(float(info.duration), 2),
            confidence=round(aggregate_confidence(segments), 4),
            segments=segments,
            model=f"faster-whisper-{self.model_name}",
            latency_ms=round(t.ms, 1),
        )

    def transcribe_bytes(self, data: bytes, language: str | None = None) -> Transcript:
        """Decode any ffmpeg-supported container (wav/mp3/m4a/webm/ogg) and transcribe."""
        return self.transcribe_array(decode_audio(data), language)


def decode_audio(data: bytes) -> np.ndarray:
    """Decode compressed or wav audio bytes to mono 16 kHz float32 using PyAV (bundled ffmpeg)."""
    from faster_whisper.audio import decode_audio as fw_decode

    return fw_decode(io.BytesIO(data), sampling_rate=SAMPLE_RATE)


def pcm16_to_float(data: bytes) -> np.ndarray:
    """Little-endian 16-bit PCM bytes → float32 in [-1, 1]."""
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0


@lru_cache
def get_stt() -> WhisperSTT:
    """Process-wide STT singleton (model from WHISPER_MODEL)."""
    s = get_settings()
    return WhisperSTT(s.whisper_model, s.device, s.whisper_compute_type)
