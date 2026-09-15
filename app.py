"""Gradio chat demo + JSON API (Hugging Face Spaces entry point).

- `/`            Gradio UI
- `/api/health`  liveness check
- `/api/chat`    JSON endpoint used by the Next.js frontend in `web/` (deployed on Vercel)
"""

import os
from typing import Literal

import gradio as gr
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag.chain import SOURCES_HEADER, OralHealthRAG, format_answer_markdown

rag = OralHealthRAG()  # loads the FAISS index + embedding model once at startup

HEADER = """# Scope Dental Practice Islamabad — Patient Assistant
Answers come **only** from Scope Dental Practice's own information and NHS/WHO patient guidance, with numbered citations you can click.
If the sources don't cover your question, it says so instead of guessing.

> ⚠️ General information only — not a diagnosis. For severe pain, facial swelling, or trouble
> breathing or swallowing, contact a dentist, doctor or emergency services straight away."""

FOOTER = """<small>Practice information: scopedental.pk. General guidance: NHS website content — contains public sector information licensed under the
Open Government Licence v3.0. WHO fact sheets — © World Health Organization, CC BY-NC-SA 3.0 IGO.
Chat model: Gemini 3.6 Flash (free tier). Embeddings: BAAI/bge-small-en-v1.5 (local).</small>"""

EXAMPLES = [
    "How long should I brush my teeth for, and should I rinse afterwards?",
    "Why do my gums bleed when I brush?",
    "When should I start brushing my baby's teeth?",
    "What are the early signs of mouth cancer?",
    "I think I have a dental abscess — what should I do?",
    "How much sugar is too much for my teeth?",
]


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # Gradio multimodal message parts
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return str(content or "")


def to_pairs(history: list[dict]) -> list[tuple[str, str]]:
    pairs, pending = [], None
    for msg in history:
        if msg["role"] == "user":
            pending = _text(msg["content"])
        elif msg["role"] == "assistant" and pending is not None:
            pairs.append((pending, _text(msg["content"]).split(SOURCES_HEADER)[0]))
            pending = None
    return pairs


def respond(message: str, history: list[dict]) -> str:
    try:
        return format_answer_markdown(rag.ask(message, to_pairs(history)))
    except Exception as exc:  # surface config/rate-limit problems in the chat instead of a blank error
        return f"⚠️ Sorry, something went wrong: `{exc}`"


with gr.Blocks(title="Scope Dental Practice Islamabad — Patient Assistant") as demo:
    gr.Markdown(HEADER)
    gr.ChatInterface(respond, examples=EXAMPLES)
    gr.Markdown(FOOTER)


# ---------------------------------------------------------------- JSON API


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=20)


class Source(BaseModel):
    n: int
    title: str
    section: str
    url: str
    publisher: str
    license: str
    score: float
    cited: bool


class ChatResponse(BaseModel):
    answer: str
    refused: bool
    sources: list[Source]
    latency_s: float


api = FastAPI(title="Oral Health RAG API")
api.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@api.get("/api/health")
def health():
    return {"status": "ok", "chunks": rag.store.index.ntotal}


@api.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, x_api_key: str | None = Header(default=None)):
    # Optional shared secret so only your frontend proxy can spend the free LLM quota.
    expected = os.getenv("API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        ans = rag.ask(req.message, to_pairs([t.model_dump() for t in req.history]))
    except RuntimeError as exc:  # missing provider key etc.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # upstream LLM errors / rate limits
        raise HTTPException(status_code=502, detail=f"Model provider error: {exc}") from exc

    return ChatResponse(
        answer=ans.answer,
        refused=ans.is_refusal,
        latency_s=ans.latency_s,
        sources=[
            Source(
                n=c["n"],
                title=c["title"],
                section=c["section"],
                url=c["url"],
                publisher=c["publisher"],
                license=c["license"],
                score=c["score"],
                cited=c["n"] in ans.cited,
            )
            for c in ans.contexts
        ],
    )


app = gr.mount_gradio_app(api, demo, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "7860")))
