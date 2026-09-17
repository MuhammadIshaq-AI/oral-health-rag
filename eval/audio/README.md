# Speech test sets

## `generated/` — synthetic proxy (committed as code, not audio)

`make audio` (`python -m eval.audio.synth`) renders every labelled gold question
with several Piper voices and four acoustic conditions:

| Condition | What it simulates |
|---|---|
| `clean` | quiet room, close microphone |
| `noise_snr10` | background noise at 10 dB SNR |
| `telephone` | 300–3400 Hz band-pass, 8 kHz sample rate |
| `slow` | slower speaking rate (`length_scale` 1.35) |

Voices are British regional and US English: **Piper has no Australian-English
voice**, so this set measures robustness to acoustic conditions and speaker
variation, *not* Australian accents. Treat the numbers as a regression baseline.

The generated WAVs and their manifest are git-ignored; regenerate them with
`make audio` (deterministic: fixed noise seeds).

## `recorded/` — real speech (never committed)

Real recordings belong here, under human research ethics approval, with the same
manifest format:

```json
{"id": "rec/pt07/q014", "question_id": "g014", "voice": "pt07", "condition": "clean",
 "source": "recorded", "path": "eval/audio/recorded/pt07/q014.wav", "reference": "..."}
```

Recommended (post-approval) sampling frame, reflecting who the service is for:
Australian English speakers across age groups (including people over 70),
Aboriginal English speakers, and speakers with Vietnamese, Mandarin, Arabic,
Greek, Italian and Hindi first languages; quiet and noisy settings; mobile and
landline audio. Store participant identifiers separately from the audio, keep a
deletion path, and record consent for reuse.

`python -m eval.run --only wer` scores whatever manifests exist, so real
recordings are reported alongside (and can replace) the synthetic set.
