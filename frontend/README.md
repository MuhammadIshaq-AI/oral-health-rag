# DentalCare AU — frontend

Voice-enabled, citation-grounded oral health information assistant for the Australian public.
React 18 + Vite + TypeScript (strict) + Tailwind CSS. No UI kit, no analytics, no external
fonts or CDNs — nothing leaves the machine except the API calls to the backend.

## Run it

```bash
npm ci          # install (uses the committed package-lock.json)
npm run dev     # Vite dev server on http://localhost:5173
```

Start the FastAPI backend on `http://localhost:8000` first. The dev server proxies
everything under `/api` to it, including the `/api/stt/stream` websocket
(`ws: true` in `vite.config.ts`). `npm run preview` serves the production build with
the same proxy.

Other scripts:

| script | what it does |
| --- | --- |
| `npm run build` | `tsc -b && vite build` → `dist/` |
| `npm run lint` | ESLint flat config (typescript-eslint + react-hooks) |
| `npm test` | Vitest unit tests (markdown/citation parsing, audio downsampling, an App render smoke test) |

To point the app at a backend on another origin, set `VITE_API_BASE` (e.g.
`VITE_API_BASE=http://localhost:8000 npm run dev`); by default all calls are same-origin.

## API endpoints used

`POST /api/session`, `POST /api/consent`, `GET /api/health`, `POST /api/chat`,
`POST /api/stt` (multipart `file`), `WS /api/stt/stream` (16 kHz mono Int16 PCM frames),
`POST /api/tts` (JSON `{ text }` → `audio/wav`; controls are hidden when
`health.tts_enabled` is false or the call fails).

## Accessibility and safety features

- **Consent gate** before first use: plain-English explanation of anonymous research
  logging, on-device audio processing, and the general-information disclaimer. Choice and
  session id are stored in `localStorage` (all storage access is wrapped in `try/catch`) and
  posted to `/api/consent`. Re-openable any time from the **Privacy** button in the header.
- **Persistent disclaimer** in the footer: *General information only — not a substitute for
  professional dental advice. In an emergency call 000.*
- **Triage alerts**: `emergency` (red) and `crisis` (deep indigo) render with `role="alert"`
  and full-width ≥56 px tap-to-call buttons; `urgent` renders an amber banner above the answer.
- **Citations**: every `[n]` marker becomes a button that opens a disclosure panel with the
  organisation, page and section, a jurisdiction badge (international sources are flagged as
  *not Australian guidance*), the retrieval date in en-AU format, the exact passage and a link
  to the source page. A compact **Sources** list sits under each answer.
- **Voice**: press-and-hold *or* tap-to-toggle microphone (≥72 px) with keyboard support
  (Space/Enter), live waveform, live partial transcript (`aria-live="polite"`), and an
  *Upload audio* fallback. Low-confidence transcripts (< 0.5) are placed in the text box with
  a "Please check what we heard" note instead of being sent automatically.
- **Text size control** (Standard / Large / Extra large) scales the whole interface via the
  root font size and is remembered; the base font is ≥18 px and tap targets are ≥48 px.
- **Read answers aloud** toggle plus a per-answer *Listen* button (server TTS).
- Semantic landmarks, visible focus rings, AA-contrast teal/slate palette, dark mode via
  `prefers-color-scheme`, and `prefers-reduced-motion` respected.

## Structure

```
src/
  api.ts                 typed client + request/response types
  App.tsx                app state: session, consent, chat turns, voice, TTS
  hooks/                 useLocalStorage, usePushToTalk (mic → WS PCM), useTts
  lib/                   markdown.ts (tiny safe parser), audio.ts (downsample/Int16),
                         chat.ts (message model, history), sources.ts (labels, safe URLs)
  components/            ConsentGate, Header, FontSizeControl, DisclaimerBanner, ChatView,
                         MessageBubble, AnswerText, CitationChip, SourceList, TriageAlert,
                         PushToTalk, Waveform, Composer, StarterQuestions,
                         ThinkingIndicator, ErrorCard
```

Answer markdown is parsed into tokens and rendered as React elements — `dangerouslySetInnerHTML`
is never used, and source/action links are restricted to `http(s)`, `tel:`, `sms:` and `mailto:`.
