# Vedic Voice Studio · वैदिक स्वर स्टूडियो

🕉️ AI-powered Sanskrit & Hindi voice cloning with Indian Classical Music composition parameters and Vedic phonetic analysis. 100% local, GPU-accelerated.

## ✨ Voice Engines

| Engine | Best For | Languages | Model Size | VRAM | Output |
|--------|----------|-----------|------------|------|--------|
| **🏛️ IndicF5** (Recommended) | Sanskrit & Hindi | 11 Indian languages | ~1.2 GB | ~2 GB | 24 kHz |
| **🌍 XTTS v2** | Multilingual + Hindi | 17 languages incl. Hindi | ~1.9 GB | ~2 GB | 24 kHz |
| **💬 Chatterbox** | Hindi + Emotions | 23 languages incl. Hindi | ~3.2 GB | ~3 GB | 24 kHz |
| **⚡ LuxTTS** | English (CPU-fast) | English only | ~1.4 GB | CPU | 48 kHz |

### IndicF5 — Why It's the Best for Sanskrit/Hindi

[IndicF5](https://huggingface.co/ai4bharat/IndicF5) by AI4Bharat (IIT Madras) is an F5-TTS variant trained on **1,400+ hours** of high-quality Indian speech across **11 languages**:

- 🇮🇳 Hindi, Bengali, Gujarati, Marathi, Punjabi
- 🇮🇳 Tamil, Telugu, Kannada, Malayalam, Odia, Assamese
- 📜 Sanskrit (via Hindi phoneme space — shared Devanagari script)

**Key advantages:**
- **Native Devanagari input** — no romanization or phonemizer needed
- **Zero-shot voice cloning** from 5–15 seconds of reference audio
- **Character-based modeling** — leverages India's phonetic orthography
- **Best voice similarity** for Indic speakers

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd vedic-voice-studio
bash install.sh
```

This installs into the Voicebox backend venv:
- `f5-tts` (IndicF5 architecture)
- `coqui-tts` (XTTS v2)
- `indic-transliteration` (IAST ↔ Devanagari)

### 2. Start the Application
```bash
bash start.sh
```

Or manually:
```bash
# Terminal 1: Start backend
cd ../voicebox
backend/venv/bin/python -m backend.main

# Terminal 2: Open UI
open index.html
```

### 3. Use the Studio
1. **Select Engine** → IndicF5 (recommended for Sanskrit/Hindi)
2. **Upload Reference Audio** → 5–15 seconds of clear speech
3. **Enter Sanskrit/Hindi Text** → Devanagari or IAST
4. **Choose Musical Parameters** → Rāga, Chhand, Tāla, Tempo
5. **Generate** → Voice cloned audio

## 📁 Project Structure

```
vedic-voice-studio/
├── index.html                        # Main web application
├── install.sh                        # Dependency installer
├── start.sh                          # Startup script
├── system_prompts/
│   ├── music_composer.md             # AI music composition spec
│   └── vedic_phonetics.md            # Vedic phonetics spec
├── README.md                         # This file
├── PROJECT_HANDOFF.md                # AI agent handoff
├── ARCHITECTURE.md                   # Technical architecture
├── RAGA_REFERENCE.md                 # 10 Rāgas documented
├── CHHANDAS_REFERENCE.md             # 9 Sanskrit meters
├── VEDIC_PHONETICS_GUIDE.md          # Complete phonetics guide
├── CONTRIBUTING.md                   # Contribution guidelines
└── CHANGELOG.md                      # Version history
```

### Backend Files (in `../voicebox/backend/`)
```
backends/
├── indicf5_backend.py                # IndicF5 voice cloning engine
├── xtts_backend.py                   # XTTS v2 voice cloning engine
└── __init__.py                       # Registry (IndicF5 + XTTS added)
utils/
└── indic_text.py                     # Sanskrit/Hindi text preprocessor
```

## 🎵 Features

### Voice Cloning
- Zero-shot cloning from 5–15s reference audio
- Drag-and-drop or click to upload
- Auto-extracts best speech segment from long recordings
- Profile management via Voicebox API

### Language Support
- **Sanskrit** (संस्कृतम्) — primary language
- **Hindi** (हिन्दी) — secondary language
- Script input: Devanāgarī / IAST / Roman
- Auto-transliteration: IAST → Devanagari

### Indian Classical Music Parameters
- 10 Rāgas (Bhairavī, Yaman, Bhairav, Mālkauṃs, etc.)
- 9 Chhandas meters (Gāyatrī through Mandākrāntā)
- 7 Tāla rhythm cycles
- 3 Tempo modes (Vilambit, Madhya, Drut)

### Vedic Phonetic Analysis
- Client-side Devanāgarī syllable decomposition
- Mātrā (beat duration) calculation with Gurū rule
- Svara (3-tone pitch) annotation
- Sthāna (articulatory position) classification
- Prāṇa (aspiration class) identification
- Chhandas meter analysis

## 🖥️ System Requirements

### Minimum (CPU mode)
- 8 GB RAM
- 3 GB free disk space
- Python 3.10+

### Recommended (GPU mode)
- NVIDIA GPU with 4+ GB VRAM (RTX 3060 / 4050+)
- 16+ GB RAM
- CUDA 11.8+ / 12.x
- Python 3.10–3.12

## 🔧 Tech Stack

- **Frontend**: Single-file HTML5/CSS3/JS (no build step)
- **Fonts**: Inter + Noto Sans Devanagari (Google Fonts CDN)
- **Backend**: Voicebox FastAPI (Python 3.12)
- **TTS Models**: IndicF5 (primary), XTTS v2, Chatterbox, LuxTTS
- **ML Framework**: PyTorch 2.2+ with CUDA/MPS support
- **Text Processing**: `indic-transliteration` for IAST ↔ Devanagari

## 📋 API Reference

The frontend connects to the Voicebox backend at `http://127.0.0.1:8000`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Backend health check |
| `/models/status` | GET | Model download/load status |
| `/models/load` | POST | Load model into memory |
| `/models/download` | POST | Download model from HuggingFace |
| `/profiles` | GET/POST | Voice profile management |
| `/profiles/{id}/samples` | POST | Upload reference audio |
| `/generate` | POST | Start voice generation |
| `/generate/{id}/status` | GET (SSE) | Generation progress |
| `/audio/{id}` | GET | Retrieve generated audio |

---

> ॐ वाग्देव्यै नमः  
> *"Salutations to Vāgdevī (Sarasvatī), Goddess of Speech"*
