# Privacy and research data handling

DentalCare AU is a research prototype. It is **local-first**: with the default
configuration, nothing you type or say leaves the machine running the software.
This document describes exactly what is processed, what is stored and how to
delete it.

## 1. What runs where

| Stage | Component | Where it runs | Leaves the machine? |
|---|---|---|---|
| Speech to text | faster-whisper (`small` by default) | Locally, on CPU or GPU | No |
| Embeddings | BAAI/bge-m3 | Locally | No |
| Reranking | BAAI/bge-reranker-v2-m3 | Locally | No |
| Vector search | Qdrant (Docker) or FAISS | Locally | No |
| Answer generation | Configurable (see below) | Local **or** an external API | Depends on config |
| Speech output | Piper TTS | Locally | No |

**Answer generation is the only stage that can leave the machine.** The default
config (`configs/default.yaml`) uses a local open-weight model through Ollama. If
you select an API provider (`configs/gemini-flash.yaml`, or any config with
provider `gemini`, `openai` or `anthropic`), then for every turn the following is
sent to that provider: your question, the recent conversation, the retrieved
public-guidance passages, and — when model triage is on — your raw message for
safety classification. Those providers have their own retention policies, which
this project does not control.

`GET /api/health` reports `local_only: true|false`, and the interface shows this
to the user. Audio is **never** sent to an API provider: only the local
transcript can be.

## 2. Identifiers

* No accounts, names, emails or logins.
* Each browser session gets a random UUID (`session_id`) with no link to a person.
* The session id and interface preferences (font size, TTS on/off, consent
  decision) are kept in the browser's `localStorage` and can be cleared by
  clearing site data.
* IP addresses are not logged by the application. A reverse proxy in front of it
  might log them; that is outside the application's control.

## 3. Consent and what is logged

Before the first question, the interface asks for a choice:

* **"Log my conversation for research"** (consent = true): the full turn record is
  stored, including the transcript, the rewritten query, the answer and the
  triage trigger phrases.
* **"Use without research logging"** (consent = false): the same turn is recorded,
  but every content field (`raw_input`, `transcript`, `rewritten_query`, `answer`,
  `triage_evidence`) and the triage trigger phrases are dropped before writing.
  Only non-content measurements remain (timings, retrieved chunk ids and scores,
  triage label, model and corpus versions, validation flags).

Consent can be changed at any time from the Privacy button; it applies to
subsequent turns.

The exact fields are defined in `api/app/telemetry/schema.py` (`TurnLog`) and
documented in the README under "Research use".

## 4. Where data is stored

| Data | Location | Notes |
|---|---|---|
| Turn logs | `data/logs/turns-YYYYMMDD.jsonl` and `data/logs/turns.db` | Append-only; git-ignored |
| Consent decisions | `consents` table in `data/logs/turns.db` | session id, decision, timestamp |
| CSV exports | `data/exports/` | Created on demand by `make export` |
| Raw corpus snapshots | `data/raw/` | Public web pages, not user data |
| Models | `data/models/`, Hugging Face cache | No user data |

**Audio is not stored.** Uploaded and streamed audio is held in memory for
transcription and discarded; only the transcript can be persisted, and only with
consent.

Nothing under `data/` is ever committed to git (see `.gitignore`).

## 5. Deleting data

```bash
make purge          # asks for confirmation, then deletes logs, the database and exports
make export         # CSV copy first, if you need one for analysis
```

`make purge` removes `data/logs/`, `data/exports/` and any cached audio. It does
not touch the corpus index or downloaded models.

## 6. Research use and ethics

* This is an information tool, not a medical device, and it does not diagnose.
* Logged data is intended for evaluating groundedness, safety triage and speech
  robustness. Any study with real participants needs human research ethics
  approval covering recruitment, consent wording, storage and retention; the
  consent screen in this repository is a prototype, not approved study text.
* Real accented speech recordings for the WER evaluation must only be collected
  under such approval, and belong in `eval/audio/recorded/` (git-ignored), not in
  the repository.
* Before sharing any exported data, re-read free-text fields: people sometimes
  type identifying details into health questions.

## 7. Security notes

* API keys live in `.env`, which is git-ignored. Never commit a key.
* The API has no authentication and is meant for localhost or a trusted network.
  Do not expose it to the public internet as-is.
* The frontend requests microphone access only while push-to-talk is held.
