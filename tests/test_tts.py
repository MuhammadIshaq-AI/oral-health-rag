"""Piper TTS text preparation and endpoint behaviour (no voice model needed)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tts.piper import speakable, voice_path


def test_speakable_strips_markup_and_reads_numbers() -> None:
    text = (
        "**Bleeding gums** can be a sign of gum disease [1][2].\n"
        "- Brush twice a day [3]\n"
        "See https://example.org/gums or call 1800 022 222"
    )
    spoken = speakable(text)
    assert "[1]" not in spoken and "**" not in spoken and "http" not in spoken
    assert spoken.startswith("Bleeding gums can be a sign of gum disease.")
    assert "Brush twice a day." in spoken
    assert "1800, 022, 222" in spoken


def test_speakable_expands_emergency_numbers() -> None:
    assert "triple zero" in speakable("Call 000 now.")
    assert "13, 11, 14" in speakable("Lifeline 13 11 14")


def test_voice_path() -> None:
    assert voice_path("en_GB-alba-medium") == "en/en_GB/alba/medium/en_GB-alba-medium"
    assert voice_path("en_US-lessac-medium") == "en/en_US/lessac/medium/en_US-lessac-medium"


class FakeTTS:
    """Returns a fixed WAV header-ish payload."""

    def synthesize(self, text: str) -> bytes:
        self.last = text
        return b"RIFF....WAVEfake"


@pytest.fixture
def client():
    app.state.tts = FakeTTS()
    # No `with`: skipping lifespan keeps the retriever and its models out of this test.
    yield TestClient(app)
    app.state.tts = None


def test_tts_endpoint_returns_wav(client: TestClient) -> None:
    r = client.post("/api/tts", json={"text": "Brush twice a day [1]."})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert r.content.startswith(b"RIFF")


def test_tts_rejects_empty_text(client: TestClient) -> None:
    assert client.post("/api/tts", json={"text": ""}).status_code == 422
