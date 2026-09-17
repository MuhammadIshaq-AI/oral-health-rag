"""STT endpoint and protocol tests with a fake engine; one real-model test marked `models`."""

from __future__ import annotations

import io
import math
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.stt.whisper import Segment, Transcript, aggregate_confidence, segment_confidence

SR = 16_000


class FakeSTT:
    """Returns a fixed transcript and records the audio lengths it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def transcribe_array(
        self, audio: np.ndarray, language: str | None = None, beam_size: int = 5
    ) -> Transcript:
        self.calls.append((len(audio), beam_size))
        seg = Segment(0.0, len(audio) / SR, "my gums bleed", -0.1, 0.01, 0.9)
        return Transcript("my gums bleed", "en", 0.99, len(audio) / SR, 0.9, [seg], "fake")


def _tone_pcm16(seconds: float) -> bytes:
    t = np.arange(int(SR * seconds)) / SR
    return (0.3 * np.sin(2 * math.pi * 220 * t) * 32767).astype("<i2").tobytes()


def _wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    return buf.getvalue()


@pytest.fixture
def fake_client():
    fake = FakeSTT()
    app.state.stt = fake
    client = TestClient(app)  # no lifespan: STT endpoints don't need the RAG state
    yield client, fake
    app.state.stt = None


def test_confidence_helpers() -> None:
    assert segment_confidence(0.0, 0.0) == 1.0
    assert 0.0 < segment_confidence(-0.5, 0.2) < 0.61
    segs = [Segment(0, 1, "a", 0, 0, 1.0), Segment(1, 4, "b", 0, 0, 0.5)]
    assert aggregate_confidence(segs) == pytest.approx(0.625)
    assert aggregate_confidence([]) == 0.0


def test_websocket_partial_and_final(fake_client) -> None:
    client, fake = fake_client
    with client.websocket_connect("/api/stt/stream") as ws:
        ws.send_json({"type": "start", "language": "en"})
        chunk = _tone_pcm16(0.25)
        for _ in range(16):  # 4 s of audio in 250 ms frames
            ws.send_bytes(chunk)
        ws.send_json({"type": "end"})
        messages = []
        while True:
            msg = ws.receive_json()
            messages.append(msg)
            if msg["type"] in ("final", "error"):
                break
    final = messages[-1]
    assert final["type"] == "final" and final["text"] == "my gums bleed"
    assert final["segments"][0]["confidence"] == 0.9 and final["language"] == "en"
    assert fake.calls[-1] == (4 * SR, 5)  # final pass uses beam search on all audio
    assert any(beam == 1 for _, beam in fake.calls[:-1])  # at least one greedy partial


def test_websocket_rejects_empty(fake_client) -> None:
    client, _ = fake_client
    with client.websocket_connect("/api/stt/stream") as ws:
        ws.send_json({"type": "end"})
        assert ws.receive_json()["type"] == "error"


def test_upload_rejects_unsupported_type(fake_client) -> None:
    client, _ = fake_client
    r = client.post("/api/stt", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_upload_wav(fake_client) -> None:
    pytest.importorskip("faster_whisper")
    client, fake = fake_client
    wav = _wav_bytes(_tone_pcm16(1.0))
    r = client.post("/api/stt", files={"file": ("q.wav", wav, "audio/wav")})
    assert r.status_code == 200 and r.json()["text"] == "my gums bleed"
    assert abs(fake.calls[-1][0] - SR) < 400


@pytest.mark.models
def test_real_whisper_on_synthesised_speech(tmp_path) -> None:
    """Needs faster-whisper + a Piper voice (make audio downloads one)."""
    from app.stt.whisper import get_stt
    from app.tts.piper import get_tts

    wav = get_tts().synthesize("How do I clean my dentures?")
    result = get_stt().transcribe_bytes(wav)
    assert "denture" in result.text.lower()
    assert result.language == "en" and 0.0 < result.confidence <= 1.0
