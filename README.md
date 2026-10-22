# Voicebox — local voice cloning

Clone a voice from a short recording and turn any text into speech in that voice. Everything runs on your Mac; nothing is sent
anywhere except the one-time model download.

This folder wraps the [Voicebox](voicebox/README.md) app (React UI + Python backend) with the **LuxTTS** engine
(48 kHz output, runs on CPU) and adds automatic voice analysis to the existing *Create Voice* dialog.

## Quick start

**Double-click `Start Voice Studio.command`** (in this folder). It starts the backend if it isn't running and opens Voicebox at
**http://localhost:8000/**. Running it again is safe. To stop it:

```bash
"$HOME/Desktop/audio editor/Start Voice Studio.command" stop
```

By hand instead (works from any folder):

```bash
cd "$HOME/Desktop/audio editor/voicebox" && backend/venv/bin/python -m backend.main
```

then open http://localhost:8000/.

> The backend serves the Voicebox UI from `voicebox/frontend`. If you change anything in `voicebox/app`, rebuild it:
> `cd voicebox && bun run build:web && rm -rf frontend && cp -R web/dist frontend` (no restart needed).
> Without that folder the launcher falls back to the older single-file page, `voicebox/voice_clone.html`.

## Creating your voice

Click **Create Voice** in Voicebox. The dialog opens on **Upload**.

1. **Upload a recording** (or switch to Record). Formats: WAV, MP3, M4A, FLAC, OGG, AAC, WebM, Opus; 2–30 seconds.
2. **It is analyzed automatically.** Voicebox transcribes the recording into *Reference Text*, then measures it and fills in a
   **Detected voice** card: voice type and pitch, speaking speed, pitch movement, tone, energy, pauses, delivery, recording clarity.
   Takes a few seconds.
3. **The Description is pre-filled** with a plain-language summary, e.g. *"Calm, steady balanced female-sounding voice with a
   medium-high pitch, brisk speaking speed (about 175 words per minute), natural pauses…"*. Edit it freely, or press
   **Use this description** to restore the suggestion. Your own text is never overwritten.
4. **Check the Reference Text.** It must match what is said in the recording: the voice engine uses it. Fix any transcription errors.
5. **Adjust Voice settings** if you want (below), give the voice a **Name** (e.g. "My Professional Voice") and click **Create Profile**.

What the analysis can and cannot do:

- **Measured from the audio:** pitch and pitch range, speaking speed (exact once the transcript is in), pauses, loudness variation,
  tone/brightness, breathiness (only on clean recordings), background noise and clipping.
- **Estimates:** words like *confident*, *warm* or *male-sounding* are heuristics over those measurements — treat them as a draft.
- **Not measured:** accent, pronunciation, emphasis, emotion. The engine copies those straight from your recording, which is why
  the recording, not the description, defines the sound.
- **The description does not change the sound.** LuxTTS has no text-instruction input, so the description is a label for you and your
  team. If the description and the recording disagree, the recording wins.

### Voice settings

Both settings are saved with the voice and applied by LuxTTS on every generation (they are hidden for other engines).

| Setting | What it does | Measured |
|---|---|---|
| **Speaking speed** (0.7×–1.3×) | Speeds up or slows down relative to the recording's own pace. 1.0 = "Same as recording". | Exact: 0.8× → 25% longer, 1.3× → 23% shorter on both test recordings; word accuracy unchanged. |
| **Voice similarity** (Standard 8 s / Detailed 15 s / Maximum 25 s) | How much of the recording the engine listens to. More = closer voice and pitch, slower generation. | Timbre error vs the reference, 5 s → 15 s → 24 s: 0.32 → 0.19 → 0.13. Detailed costs roughly 30–45% more generation time than Standard. |

**Advanced** holds the repo's existing controls: Personality, Default Engine and Default Effects (effects can now be chosen
while creating a voice, not only afterwards).

There is deliberately no "style / expression" slider: LuxTTS has nothing that implements one, so it would be a fake control.
Style comes from the recording. (Qwen-based engines do take style instructions, in the generate box.)

## Models are downloaded once, then reused

On first use Voicebox downloads the model from Hugging Face with live progress, then keeps it in the standard cache:

| What | Source | Size |
|---|---|---|
| LuxTTS weights | `YatharthS/LuxTTS` | ~1.1 GB |
| Whisper (transcribes references) | `openai/whisper-base` | ~0.3 GB |

- Cache folder: `~/.cache/huggingface/hub` (override with `HF_HUB_CACHE`).
- After that it loads **offline** (the backend logs `luxtts is cached — forcing offline mode`); restarting the server leaves the
  cache untouched. A model counts as downloaded only when both repos are present.
- Analysed voices are cached on disk too, so the same recording is only analysed once.

## Speed and accuracy

Measured on the development machine (Intel i5-7400, 4 cores, 8 GB RAM, no usable GPU):

| | |
|---|---|
| Model load (once per server start) | ~10 s |
| Voice analysis | ~2–8 s |
| Generation at **Detailed** (default) | ~1.3–1.5× real time (a minute of speech takes ~1.5 minutes) |
| Generation at **Standard** | ~1× real time |
| Intelligibility (Whisper-transcribed word errors) | ~1–6% |

Things chosen from measurements, not defaults:

- **CPU, not the GPU.** MPS crashes during generation on this machine (PyTorch 2.2), so LuxTTS uses its CPU/ONNX path.
- **The recording's own pace.** The library silently speaks 30% faster than the recording (≈315 wpm on a 175 wpm speaker, with dropped
  words); this is cancelled so the output keeps the reference pace.
- **The saved transcript drives the prompt.** The engine used to run Whisper on a slice of the recording; on a real recording that gave
  a 2,655-token hallucination (0.4 s of audio) at one length and half the words at another. Voicebox now uses the transcript saved with
  the voice, cut at a pause. If it is missing or implausible, Whisper transcribes the *whole* recording instead (never a slice), and a
  transcript that still looks wrong is refused with a message rather than producing bad audio.
- **500-character chunks.** For LuxTTS, long text is split at 500 characters whatever the app's setting says: 800 was 2.3× slower.
- **The speed setting is calibrated.** The engine's own speed knob is wildly non-linear (its 1.3 shortened speech 3×); it is inverted
  so that 1.15× really means 15% faster.

Long texts take a while: a 6,500-word speech is about 35 minutes of audio. The generation keeps running if you leave the page.

## Reference audio tips

- One speaker, clear speech, little background noise or music, 10–30 seconds.
- Make sure the Reference Text matches the audio word for word.
- Other engines (Qwen, Chatterbox…) appear in Voicebox but were not tested here; they need far larger downloads and more RAM.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Can't open the page | Run `Start Voice Studio.command`, then open exactly `http://localhost:8000/`. |
| Page says the server is offline | The backend stopped. Run the launcher again, or check `curl http://127.0.0.1:8000/health`. |
| Launcher says a port is in use | Something else uses 8000. Stop it, or run with `BACKEND_PORT=8010 "./Start Voice Studio.command"`. |
| "Could not transcribe the reference recording reliably" | Open the voice, correct its Reference Text so it matches the audio, and retry. |
| Voice analysis fails | The recording is empty, silent or has too little speech. Try a clearer recording. |
| Code changes have no effect | The backend does not auto-reload. Restart it (stop, then run the launcher). |
| Download looks stuck at "Connecting to HuggingFace" | Needs internet for the first download only. |

## Project layout

```
Start Voice Studio.command          one-click launcher (backend + opens the UI)
voicebox/app/                       Voicebox React UI (the Create Voice dialog: components/VoiceProfiles/)
voicebox/frontend/                  built UI the backend serves (generated; not in git)
voicebox/backend/                   FastAPI server (python -m backend.main, port 8000)
  services/voice_analysis.py          measures a recording, writes the description
  routes/profiles.py                  POST /profiles/analyze
  backends/luxtts_backend.py          LuxTTS engine: device, prompt/transcript, speed, chunk limit
voicebox/voice_clone.html           older single-file page (fallback)
```

## Tests and checks

```bash
cd "$HOME/Desktop/audio editor/voicebox"
backend/venv/bin/python -m pytest backend/tests -q \
  --ignore=backend/tests/test_all_models_e2e.py \
  --ignore=backend/tests/test_audioop_python313.py \
  --ignore=backend/tests/test_rocm_build.py
bun run typecheck          # React app and web build
bunx biome check app/src/components/VoiceProfiles
```

The three ignored backend tests need model downloads or PyInstaller. New tests: `test_voice_analysis.py`, `test_voice_settings.py`,
`test_luxtts_prompt.py`, `test_luxtts_cache.py`.
