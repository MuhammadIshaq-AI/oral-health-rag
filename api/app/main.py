"""FastAPI application: chat, speech-to-text, sessions/consent, health."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import enable_system_tls, get_settings
from app.experiments import load_experiment
from app.llm.factory import is_local, make_llm
from app.rag.retriever import Retriever
from app.schemas import ChatRequest, ChatResponse, ConsentIn, HealthOut, SessionOut
from app.service import AppState, handle_turn
from app.stt.stream import STTEngine, stream_session
from app.telemetry.logger import ResearchLogger

log = logging.getLogger("dentalcare")


async def build_state() -> AppState:
    """Load config, LLM client, retriever and logger."""
    enable_system_tls()
    settings = get_settings()
    cfg = load_experiment(settings.experiment_config)
    try:
        retriever: Retriever | None = Retriever.from_settings(settings)
    except FileNotFoundError:
        log.warning("No index found under %s — run `make ingest`", settings.index_dir)
        retriever = None
    logger = ResearchLogger(settings.log_dir)
    await logger.init()
    return AppState(
        settings=settings,
        cfg=cfg,
        llm=make_llm(cfg.llm, settings),
        retriever=retriever,
        logger=logger,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create shared state once; warm up models so the first request is fast."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not hasattr(app.state, "svc"):
        app.state.svc = await build_state()
        svc: AppState = app.state.svc
        if svc.retriever is not None:
            try:
                svc.retriever.retrieve("warm up bleeding gums", svc.cfg.retrieval)
            except Exception as exc:  # model download / store problems shouldn't block startup
                log.warning("Warm-up failed: %s", exc)
    yield


app = FastAPI(title="DentalCare AU API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def svc(request: Request) -> AppState:
    """Shared application state."""
    return request.app.state.svc


@app.get("/api/health", response_model=HealthOut)
async def health(request: Request) -> HealthOut:
    """Service, model and corpus status."""
    s = svc(request)
    return HealthOut(
        status="ok" if s.retriever else "no_index",
        model=s.llm.model,
        provider=s.llm.provider,
        local_only=is_local(s.cfg.llm),
        corpus_version=s.corpus_version,
        n_chunks=len(s.retriever.chunks) if s.retriever else 0,
        vector_store=s.retriever.store_name if s.retriever else None,
        retrieval_mode=s.cfg.retrieval.mode,
        config_name=s.cfg.name,
        config_hash=s.cfg.config_hash,
        prompt_version=s.cfg.prompt_version,
        tts_enabled=s.settings.tts_enabled,
        whisper_model=s.settings.whisper_model,
    )


@app.post("/api/session", response_model=SessionOut)
async def new_session() -> SessionOut:
    """Issue a random, non-identifying session id."""
    return SessionOut(session_id=uuid.uuid4().hex)


@app.post("/api/consent")
async def consent(body: ConsentIn, request: Request) -> dict[str, bool]:
    """Record the user's research-logging consent decision."""
    await svc(request).logger.set_consent(body.session_id, body.consent)
    return {"ok": True}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """Answer one user turn."""
    try:
        return await handle_turn(svc(request), body)
    except RuntimeError as exc:
        log.exception("chat failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ---- Speech-to-text ---------------------------------------------------------
ALLOWED_AUDIO = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".mp4", ".flac"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def stt_engine(request: Request | WebSocket) -> STTEngine:
    """Shared Whisper model (loaded on first use; tests may inject `app.state.stt`)."""
    if getattr(request.app.state, "stt", None) is None:
        from app.stt.whisper import get_stt

        request.app.state.stt = get_stt()
    return request.app.state.stt


@app.post("/api/stt")
async def transcribe_upload(request: Request, file: UploadFile = File(...)) -> dict[str, object]:
    """Transcribe an uploaded audio file (wav/mp3/m4a/webm/ogg) with local faster-whisper."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix and suffix not in ALLOWED_AUDIO:
        raise HTTPException(status_code=415, detail=f"Unsupported audio type {suffix}")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (25 MB max)")
    engine = stt_engine(request)
    try:
        from app.stt.whisper import decode_audio

        audio = await asyncio.to_thread(decode_audio, data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not decode audio: {exc}") from exc
    result = await asyncio.to_thread(engine.transcribe_array, audio, None, 5)
    return result.to_dict()


@app.websocket("/api/stt/stream")
async def transcribe_stream(ws: WebSocket) -> None:
    """Push-to-talk streaming transcription (see app.stt.stream for the protocol)."""
    await ws.accept()
    engine = await asyncio.to_thread(stt_engine, ws)
    await stream_session(ws, engine)
    await ws.close()
