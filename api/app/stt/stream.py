"""WebSocket streaming transcription protocol.

Client → server
  * binary frames: little-endian 16-bit mono PCM at 16 kHz (the browser resamples)
  * text frame ``{"type": "start", "language": "en"}`` (optional)
  * text frame ``{"type": "end"}`` when push-to-talk is released

Server → client
  * ``{"type": "partial", "text": ...}`` roughly every ``partial_interval_s`` of new audio
  * ``{"type": "final", ...Transcript}`` after ``end``
  * ``{"type": "error", "message": ...}``

Partials re-decode the whole utterance with greedy search (cheap for push-to-talk
lengths); the final pass uses beam search for accuracy.
"""

from __future__ import annotations

import asyncio
import json
from typing import Protocol

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect

from app.stt.whisper import SAMPLE_RATE, Transcript, pcm16_to_float

MAX_SECONDS = 60


class STTEngine(Protocol):
    """Subset of WhisperSTT used by the stream handler."""

    def transcribe_array(
        self, audio: np.ndarray, language: str | None = None, beam_size: int = 5
    ) -> Transcript:
        """Transcribe float32 PCM."""
        ...


async def stream_session(
    ws: WebSocket, stt: STTEngine, partial_interval_s: float = 1.5
) -> Transcript | None:
    """Run one push-to-talk utterance over an accepted WebSocket."""
    buffer = bytearray()
    language: str | None = None
    last_partial_len = 0
    partial_task: asyncio.Task[Transcript] | None = None
    step = int(partial_interval_s * SAMPLE_RATE) * 2  # bytes of int16

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                return None
            if (data := msg.get("bytes")) is not None:
                buffer.extend(data)
                if len(buffer) > MAX_SECONDS * SAMPLE_RATE * 2:
                    await ws.send_json(
                        {"type": "error", "message": f"Recording longer than {MAX_SECONDS}s"}
                    )
                    return None
                ready = partial_task is None or partial_task.done()
                if partial_task is not None and partial_task.done():
                    await ws.send_json({"type": "partial", "text": partial_task.result().text})
                    partial_task = None
                if ready and len(buffer) - last_partial_len >= step:
                    last_partial_len = len(buffer)
                    audio = pcm16_to_float(bytes(buffer))
                    partial_task = asyncio.create_task(
                        asyncio.to_thread(stt.transcribe_array, audio, language, 1)
                    )
                continue
            payload = json.loads(msg.get("text") or "{}")
            if payload.get("type") == "start":
                language = payload.get("language") or None
            elif payload.get("type") == "end":
                if partial_task is not None:
                    partial_task.cancel()
                if len(buffer) < SAMPLE_RATE // 5:  # < 0.1 s of audio
                    await ws.send_json({"type": "error", "message": "No audio received"})
                    return None
                result = await asyncio.to_thread(
                    stt.transcribe_array, pcm16_to_float(bytes(buffer)), language, 5
                )
                await ws.send_json({"type": "final", **result.to_dict()})
                return result
    except WebSocketDisconnect:
        return None
