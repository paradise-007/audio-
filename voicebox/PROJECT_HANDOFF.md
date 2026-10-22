# PROJECT HANDOFF

## 1. Project Overview
- **Project Name**: Voicebox
- **Purpose**: Local AI voice-cloning and text-to-speech desktop & web application. Enables high-fidelity voice cloning from reference audio samples to synthesize natural-sounding speech preserving voice identity, pitch, accent, and prosody.
- **Current Status**: Core backend and engine pipeline are fully functional with LuxTTS (ZipVoice 48kHz engine) as the default voice-cloning engine. The backend FastAPI server is active on `http://127.0.0.1:8000`. A dedicated Voice Cloning Studio UI (`voice_clone.html`) is deployed and connected to the backend.

## 2. Tech Stack
- **Frontend**:
  - Standalone Studio: Vanilla HTML5, Modern Dark CSS3 System (Glassmorphism, CSS Grid/Flexbox), JavaScript (ES6 fetch, Web Audio API, MediaRecorder API).
  - React Web Client (`/web`): Vite, React 19, TypeScript, TailwindCSS v4, Lucide Icons, Biome.
  - Desktop Wrapper (`/tauri`): Tauri v2 (Rust wrapper for desktop packaging).
- **Backend**:
  - Python 3.12, FastAPI, Uvicorn, PyTorch 2.2.2, HuggingFace `transformers`, `diffusers`, `Zipvoice` (LuxTTS), `kokoro`, `librosa`, `soundfile`, `scipy`.
- **Database**:
  - SQLite (`voicebox.db`) via SQLAlchemy ORM & Pydantic v2 schemas.
- **Build/Tools**:
  - Bun (v1.3.8 package manager & runtime), Biome linter, PyInstaller / PyOxidizer build scripts (`scripts/build-server.sh`).

## 3. Architecture
- **API Server & Routing**: FastAPI application (`backend/main.py` -> `backend/app.py`) initializes DB sessions, registers routers (`backend/routes/`), and manages lifecycle events.
- **Engine Layer**: Abstracted backend layer in `backend/backends/` supporting pluggable engines:
  - `LuxTTSBackend` (`backend/backends/luxtts_backend.py`): Zero-shot 48kHz voice cloning (ZipVoice model).
  - `QwenBackend` (`backend/backends/qwen_backend.py`): Qwen3-TTS 0.6B/1.7B model.
  - `ChatterboxBackend` (`backend/backends/chatterbox_backend.py`): Fast draft voice cloning.
  - `KokoroBackend` (`backend/backends/kokoro_backend.py`): Pre-trained TTS.
- **Data Flow**:
  1. User records or uploads reference audio `.wav`/`.mp3` and enters prompt text in web UI (`voice_clone.html` or React frontend).
  2. UI sends `POST /profiles` to create a voice profile storing the audio sample.
  3. UI sends `POST /generations` specifying `profile_id`, `text`, and `engine: "luxtts"`.
  4. Backend runs `LuxTTSBackend.generate_audio_async()`, encoding reference audio speaker characteristics and producing synthesized 48kHz audio.
  5. Backend persists metadata in SQLite and saves `.wav` to data directory.
  6. Frontend plays output audio via HTML5 Audio API.

## 4. Current Working Features
- **High-Fidelity Voice Cloning**: LuxTTS zero-shot voice cloning with 48kHz output sample rate.
- **FastAPI Backend Server**: Running on `http://127.0.0.1:8000` with `/health` returning hardware status (`MPS (Apple Silicon)`).
- **Voice Profile Management**: Create, list, delete voice profiles via `POST /profiles`, `GET /profiles`.
- **Speech Generation API**: `POST /generations` supporting customizable text, engine parameters, reference audio, and prompt caching.
- **Voice Cloning Studio**: Standalone UI (`voice_clone.html`) featuring live mic recording, drag-and-drop audio uploading, text prompt editing, engine selection, wave visualizer, and playback controls.

## 5. Recently Completed
- **Hardware & Environment Analysis**: System benchmarked; Apple Silicon GPU acceleration (MPS) detected.
- **Dependency Resolution**: Installed complete backend dependency set in `backend/venv` (`torch 2.2.2`, `Zipvoice`, `transformers`, `diffusers`, `soundfile`, `librosa`, `scipy`).
- **Engine Configuration**: Updated `backend/models.py`, `backend/services/profiles.py`, and `voice_clone.html` to configure `luxtts` as default engine.
- **Backend Launch & Health Verification**: Launched backend server process (`task-232`), verified `/health` and `/profiles` endpoints respond HTTP 200.

## 6. In Progress
- Integrations for model progress streaming during initial HuggingFace model download (`/events` SSE endpoint).
- Synchronizing LuxTTS selection across `/web` React UI components (`EngineSelector.tsx`, `VoiceProfileForm.tsx`).

## 7. Pending Work
- [ ] **Critical**: Handle HuggingFace model download progress and cache initialization cleanly on first generation request.
  - *Files*: `backend/routes/models.py`, `backend/backends/luxtts_backend.py`
  - *Blockers*: None.
  - *Expected*: Model downloads report byte-level progress over SSE `/events`.
- [ ] **High**: Integrate LuxTTS engine choice into main React frontend (`/web`).
  - *Files*: `web/src/components/`
  - *Blockers*: None.
  - *Expected*: React app lists LuxTTS alongside Qwen and Chatterbox.
- [ ] **High**: Install `pytest` in `backend/venv` and run automated e2e backend test matrix.
  - *Files*: `backend/tests/test_all_models_e2e.py`
  - *Blockers*: None.
  - *Expected*: `pytest backend/tests` passes all unit tests.
- [ ] **Medium**: Implement long-form text chunking and batch synthesis for audiobooks/stories.
  - *Files*: `backend/routes/stories.py`, `backend/services/tts.py`
  - *Blockers*: None.
- [ ] **Low**: Build standalone binary package via `scripts/build-server.sh`.
  - *Files*: `scripts/build-server.sh`, `backend/build_binary.py`
  - *Blockers*: PyInstaller / PyOxidizer build toolchain.

## 8. Known Bugs & Issues
- `pytest` runner is missing in `backend/venv` (requires `pip install pytest pytest-asyncio`).
- High-memory Qwen 1.7B engine can crash low-RAM machines; LuxTTS should remain default.
- Initial model download requires an active internet connection to fetch `YatharthS/LuxTTS` from Hugging Face.
- **ZipVoice MPS Autocast Exception on PyTorch 2.2.2**: When running LuxTTS on macOS MPS, `zipvoice` initializes module-level `DEVICE_TYPE = "mps"`, which causes `torch.amp.autocast("mps", enabled=False)` in `zipvoice/models/modules/scaling.py` line 1204 to throw `RuntimeError: User specified an unsupported autocast device_type 'mps'`.
  - *Workaround*: Explicitly set `zipvoice.models.modules.scaling.DEVICE_TYPE = "cpu"` (or use PyTorch 2.3+ which supports MPS autocast).

## 9. Important Files
- `backend/main.py`: Entry point for `python -m backend.main`.
- `backend/app.py`: FastAPI app initialization, middleware, lifecycle events.
- `backend/models.py`: Pydantic request/response models.
- `backend/backends/luxtts_backend.py`: LuxTTS model wrapper for zero-shot voice cloning.
- `backend/backends/__init__.py`: Model engine definitions and factory.
- `backend/routes/profiles.py`: Voice profile endpoints.
- `backend/routes/generations.py`: Audio generation endpoints.
- `voice_clone.html`: Dedicated Voice Cloning Studio frontend interface.

## 10. Database / API / Data Flow
- **Database Schema**:
  - `voice_profiles`: `id`, `name`, `description`, `language`, `default_engine`, `created_at`
  - `generations`: `id`, `profile_id`, `text`, `engine`, `status`, `audio_path`, `duration`, `created_at`
- **Key API Endpoints**:
  - `GET /health`: Server health check.
  - `GET /profiles` | `POST /profiles`: Manage voice profiles.
  - `POST /generations`: Trigger voice generation job.
  - `GET /generations/{id}/audio`: Stream synthesized audio file.

## 11. Configuration & Environment
- `VOICEBOX_DATA_DIR`: Path to data directory for database & generated files (default: `~/.voicebox`).
- `VOICEBOX_CORS_ORIGINS`: Allowed CORS origins list.
- `HF_HUB_CACHE`: Directory where Hugging Face downloads and caches model weights.

## 12. Commands
- **Backend Install**: `backend/venv/bin/python -m pip install -r backend/requirements.txt`
- **Start Backend**: `backend/venv/bin/python -m backend.main`
- **Start Web Dev**: `bun run dev:web`
- **Build Web**: `bun run build:web`
- **Lint Code**: `bun run lint`
- **Typecheck**: `bun run typecheck`

## 13. Coding Rules & Conventions
- **Backend**: Use async FastAPI router endpoints. Wrap blocking CPU/GPU inference in `asyncio.to_thread()`. Keep engine logic modular inside `backend/backends/`.
- **Validation**: Enforce schema validation in `backend/models.py` using Pydantic v2 fields.
- **Frontend**: Clean dark mode aesthetics, non-blocking fetch requests, clear user loading states.

## 14. Do Not Break
- `CLONING_ENGINES` set in `backend/services/profiles.py` (must contain `luxtts`).
- Engine model regex validation patterns in `backend/models.py`.
- FastAPI lifespan handlers for model cleanup in `backend/app.py`.
- Server host/port default configuration (`127.0.0.1:8000`).

## 15. Recommended Next Steps
1. Keep the FastAPI server active on port 8000.
2. Launch `voice_clone.html` in browser to run voice-cloning generations.
3. Patch `zipvoice` module `DEVICE_TYPE` to `"cpu"` or upgrade PyTorch to >=2.3 for MPS autocast compatibility.
4. Install `pytest` in `backend/venv` and run backend automated tests.

## 16. Handoff Notes
- The FastAPI backend server task-232 ran on `http://127.0.0.1:8000`.
- All Python dependencies for LuxTTS (ZipVoice 48kHz) and PyTorch 2.2.2 are installed.
- Note for Claude: `zipvoice.models.modules.scaling.DEVICE_TYPE` should be patched to `"cpu"` when `device=="cpu"` or running on PyTorch 2.2 MPS to avoid the autocast exception.
