# PROJECT HANDOFF — Vedic Voice Studio

## 1. Project Overview
- **Project Name**: Vedic Voice Studio (वैदिक स्वर स्टूडियो)
- **Purpose**: AI-powered Sanskrit & Hindi voice cloning with Indian Classical Music composition parameters and Vedic phonetic analysis. Frontend connects to the Voicebox backend for TTS inference.
- **Current Status**: Frontend fully built with 4-engine selector. Backend has IndicF5 and XTTS v2 engines registered and instantiation-tested. Ready for end-to-end testing on a CUDA-capable machine (i7 / 32GB / RTX 4050).

## 2. Tech Stack
- **Frontend**: Single-file HTML5/CSS3/JS application (`index.html`)
- **Fonts**: Inter + Noto Sans Devanagari (Google Fonts CDN)
- **Backend**: Voicebox FastAPI server (Python 3.12, PyTorch 2.2+)
- **TTS Engines**: IndicF5 (primary), XTTS v2, Chatterbox, LuxTTS
- **Text Processing**: `indic-transliteration` for IAST ↔ Devanagari
- **Database**: SQLite via SQLAlchemy (managed by Voicebox)
- **No build step**: Open `index.html` directly in browser

## 3. Architecture
```
┌──────────────────────────────────────────┐
│   Vedic Voice Studio (Browser)           │
│  index.html — single-file app            │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ Engine Selector                    │  │
│  │ IndicF5 │ XTTS v2 │ Chat │ Lux   │  │
│  └────┬───────────────────────────────┘  │
│       │                                  │
│  ┌────┴──────┐  ┌────────────────────┐  │
│  │ Voice     │  │ Vedic Phonetics    │  │
│  │ Cloning   │  │ Engine (JS)        │  │
│  │ UI        │  │ mātrā/svara/sthāna │  │
│  └────┬──────┘  └────────────────────┘  │
│       │                                  │
│  ┌────┴─────────────────────────────┐   │
│  │ Musical Parameters               │   │
│  │ Rāga · Chhand · Tāla · Tempo    │   │
│  └────┬─────────────────────────────┘   │
└───────┼──────────────────────────────────┘
        │ HTTP/SSE
        ▼
┌──────────────────────────────────────────┐
│   Voicebox Backend (FastAPI :8000)       │
│                                          │
│   IndicF5 · XTTS v2 · Chatterbox · Lux  │
│   indic_text.py preprocessor             │
│   SQLite · HuggingFace Hub              │
└──────────────────────────────────────────┘
```

## 4. Current Working Features
- **Engine Selector**: 4-engine UI (IndicF5, XTTS v2, Chatterbox, LuxTTS) with info panel
- **Reference Audio Upload**: Drag-and-drop, auto-segment extraction for long files
- **Sanskrit/Hindi Text Input**: Devanāgarī input with IAST and Roman script toggles
- **Vedic Phonetic Analysis**: Client-side syllable breakdown (mātrā, svara, sthāna, prāṇa)
- **Musical Parameter Selection**: Rāga (10), Chhand (9 meters), Tāla (7 cycles), Tempo (3 speeds)
- **Voice Cloning Pipeline**: Profile creation, sample upload, generation, SSE progress, playback/download
- **Backend Integration**: IndicF5 and XTTS v2 backends registered, instantiation verified
- **Text Preprocessing**: Server-side Indic text processor (script detection, transliteration, chunking)

## 5. Recently Completed (v0.2.0)
- **IndicF5 backend** (`indicf5_backend.py`) — AI4Bharat F5-TTS, 11 Indian languages
- **XTTS v2 backend** (`xtts_backend.py`) — Coqui, 17 languages incl. Hindi
- **Indic text preprocessor** (`utils/indic_text.py`) — script detection, IAST↔Devanagari, pāda chunking
- **Engine selector UI** — 4-engine panel with engine-specific language mapping
- **Backend registry** — 12 Indic language codes + 2 new engine registrations
- **Install/start scripts** — `install.sh` and `start.sh` with proper path quoting

## 6. In Progress
- None — code complete, awaiting testing on CUDA machine

## 7. Pending Work
- [ ] **Critical**: Install `f5-tts` and `coqui-tts` on the target machine (i7/32GB/RTX 4050)
  - *Command*: `bash install.sh`
  - *Note*: These are large packages (~500MB each), need 32GB RAM machine for smooth install
- [ ] **Critical**: Test end-to-end voice cloning with Sanskrit Devanāgarī text
  - *Engine*: IndicF5 (primary) or XTTS v2 (backup)
  - *Model download*: ~1.2 GB from HuggingFace on first use
- [ ] **High**: Build Indian Classical Music composition backend
  - *What*: Generate Rāga-based melodies and backing tracks
  - *Files*: New backend module needed
- [ ] **Medium**: Add browser microphone recording
  - *Files*: `index.html`
  - *Reference*: `voice_clone.html` has a working implementation
- [ ] **Medium**: Enhance Sandhi analysis with contextual rules
- [ ] **Low**: Add Sāma Veda 7-svara mode

## 8. Known Bugs & Issues
- **f5-tts install slow on 8GB RAM**: pip dependency resolution takes 10+ minutes; install on 32GB machine
- **Musical params not consumed**: Rāga/Tāla/Chhand captured in UI but no backend composition engine exists
- **Phonetic analysis approximate**: Simplified svara 4-cycle pattern, not parsed from actual accent marks
- **Halanta edge cases**: Triple-conjunct consonants may not decompose correctly

## 9. Important Files

### Vedic Voice Studio
| File | Purpose |
|------|---------|
| `index.html` | Complete single-file web application |
| `install.sh` | Dependency installer (f5-tts, coqui-tts, indic-transliteration) |
| `start.sh` | Backend startup + browser open |
| `system_prompts/music_composer.md` | AI music composition spec |
| `system_prompts/vedic_phonetics.md` | Vedic phonetics spec |

### Backend Files (in `../voicebox/backend/`)
| File | Purpose |
|------|---------|
| `backends/indicf5_backend.py` | IndicF5 voice cloning engine (AI4Bharat, 11 Indian langs) |
| `backends/xtts_backend.py` | XTTS v2 voice cloning engine (Coqui, 17 langs) |
| `backends/__init__.py` | Engine registry (IndicF5 + XTTS registered) |
| `utils/indic_text.py` | Sanskrit/Hindi text preprocessor |

## 10. Database / API / Data Flow
- **No own database** — relies on Voicebox backend SQLite
- **Profile name**: Creates profiles named `"Vedic Voice Session"`
- **Language mapping**: Engine-aware via `getApiLanguage()`:
  - IndicF5: passes `sa`/`hi` directly
  - XTTS v2: maps `sa` → `hi`
  - Chatterbox: maps `sa` → `hi`
  - LuxTTS: always sends `en`
- **API base**: `http://127.0.0.1:8000` (configurable via `?api=` URL parameter)

## 11. Configuration & Environment
- **No server-side config needed** — pure frontend
- **Backend dependency**: Voicebox at `http://127.0.0.1:8000`
- **Google Fonts CDN**: Requires internet for font loading
- **Target hardware**: i7 / 32GB RAM / RTX 4050 (CUDA)

## 12. Commands
```bash
# Install dependencies (one-time)
bash install.sh

# Start backend + open UI
bash start.sh

# Or manually:
cd ../voicebox && backend/venv/bin/python -m backend.main  # Terminal 1
open index.html                                              # Terminal 2
```

## 13. Coding Rules & Conventions
- **Single-file frontend**: All HTML, CSS, and JS live in `index.html`
- **Devanāgarī-first**: UI labels include both English and Devanāgarī
- **Saffron/gold palette**: Use `--accent`, `--saffron`, `--gold` CSS variables
- **Font stack**: `'Noto Sans Devanagari'` for Indic; `'Inter'` for Latin
- **Backend pattern**: Follow existing backend protocol (`TTSBackend`) — see other backends
- **Engine registration**: Add to `TTS_ENGINES`, `_get_indic_tts_configs()`, factory in `__init__.py`

## 14. Do Not Break
- Engine model name mapping (`ENGINE_MODEL` in JS, `ModelConfig` in Python)
- Profile name `"Vedic Voice Session"`
- API base URL resolution from `?api=` query parameter
- Voicebox API endpoint signatures
- Devanāgarī vowel/consonant lookup tables
- `LANGUAGE_CODE_TO_NAME` entries for Indic languages

## 15. Recommended Next Steps
1. Install dependencies on target machine: `bash install.sh`
2. Start backend: `bash start.sh`
3. Test IndicF5 end-to-end with Gayatri Mantra
4. If IndicF5 fails, fall back to Chatterbox (already installed, supports Hindi)
5. Add browser microphone recording
6. Build music composition engine (long-term)
