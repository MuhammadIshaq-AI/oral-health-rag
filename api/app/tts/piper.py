"""Optional local text-to-speech with Piper (ONNX voices, CPU-friendly)."""

from __future__ import annotations

import io
import re
import threading
import wave
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

VOICES_REPO = "rhasspy/piper-voices"


def voice_path(voice: str) -> str:
    """Repository path for a voice id like 'en_GB-alba-medium'."""
    lang_region, name, quality = voice.split("-", 2)
    return f"{lang_region.split('_')[0]}/{lang_region}/{name}/{quality}/{voice}"


def ensure_voice(voice: str, models_dir: Path) -> Path:
    """Download the voice (.onnx + .onnx.json) into models_dir/piper if missing."""
    target = models_dir / "piper" / f"{voice}.onnx"
    if target.exists() and target.with_suffix(".onnx.json").exists():
        return target
    from huggingface_hub import hf_hub_download

    target.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".onnx", ".onnx.json"):
        downloaded = hf_hub_download(VOICES_REPO, voice_path(voice) + suffix)
        (target.parent / f"{voice}{suffix}").write_bytes(Path(downloaded).read_bytes())
    return target


_MARKUP = [
    (re.compile(r"[ \t]*\[\d{1,2}\]"), ""),  # citation markers
    (re.compile(r"https?://\S+"), ""),  # URLs
    (re.compile(r"\*\*|__|`|#+ "), ""),  # markdown emphasis / headings
    (re.compile(r"^\s*[-*•]\s+", re.MULTILINE), ""),  # bullets
    (re.compile(r"\b000\b"), "triple zero"),
    (re.compile(r"\b1800 022 222\b"), "1800, 022, 222"),
    (re.compile(r"\b13 11 14\b"), "13, 11, 14"),
    (re.compile(r"[ \t]+"), " "),
    (re.compile(r" +([.,;:!?])"), r"\1"),  # tidy gaps left by removals
]


def speakable(text: str) -> str:
    """Strip citations, URLs and markdown so the voice reads naturally."""
    for pattern, repl in _MARKUP:
        text = pattern.sub(repl, text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(ln if ln.endswith((".", "!", "?", ":")) else ln + "." for ln in lines)


class PiperTTS:
    """Thread-safe Piper voice producing 16-bit mono WAV bytes."""

    def __init__(self, voice: str, models_dir: Path) -> None:
        from piper import PiperVoice

        self.voice_name = voice
        self.voice = PiperVoice.load(ensure_voice(voice, models_dir))
        self._lock = threading.Lock()

    @property
    def sample_rate(self) -> int:
        """Output sample rate of the voice."""
        return int(self.voice.config.sample_rate)

    def synthesize(self, text: str, length_scale: float | None = None) -> bytes:
        """Return WAV bytes for `text` (citations/markdown removed)."""
        from piper import SynthesisConfig

        buf = io.BytesIO()
        with self._lock, wave.open(buf, "wb") as wav:
            self.voice.synthesize_wav(
                speakable(text), wav, syn_config=SynthesisConfig(length_scale=length_scale)
            )
        return buf.getvalue()


@lru_cache(maxsize=8)
def get_tts(voice: str | None = None) -> PiperTTS:
    """Cached voice instances (default from PIPER_VOICE)."""
    s = get_settings()
    return PiperTTS(voice or s.piper_voice, s.models_dir)
