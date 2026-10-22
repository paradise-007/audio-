# Contributing — Vedic Voice Studio

## How to Contribute

Thank you for your interest in contributing to Vedic Voice Studio! This project combines AI voice cloning technology with traditional Indian Classical Music theory and Vedic phonetics.

---

## Project Structure

```
vedic-voice-studio/
├── index.html                    # Main application (HTML + CSS + JS)
├── system_prompts/
│   ├── music_composer.md         # AI music composition prompt
│   └── vedic_phonetics.md        # Vedic phonetics analysis prompt
├── README.md                     # Project overview
├── PROJECT_HANDOFF.md            # AI agent handoff document
├── ARCHITECTURE.md               # Technical architecture
├── RAGA_REFERENCE.md             # Rāga documentation
├── CHHANDAS_REFERENCE.md         # Sanskrit prosody reference
├── VEDIC_PHONETICS_GUIDE.md      # Phonetics guide
├── CONTRIBUTING.md               # This file
└── CHANGELOG.md                  # Version history
```

---

## Areas of Contribution

### 1. Sanskrit Phonetics Engine
- Improve the client-side Devanāgarī syllable decomposition
- Add full Sandhi detection (Svara, Visarga, Consonant)
- Implement contextual svara (pitch) assignment from Vedic accent marks
- Add support for Sāma Veda 7-svara system

### 2. Music Theory
- Add more Rāgas to the selection list
- Implement Rāga recognition from text content
- Create automatic Chhand detection from syllable counts
- Add Gaṇa-based meter analysis

### 3. Frontend UI
- Add browser microphone recording (MediaRecorder API)
- Improve mobile responsiveness
- Add dark/light theme toggle
- Add visual Rāga scale diagram
- Add interactive tāla visualization

### 4. Backend Integration
- Implement a Sanskrit phonemizer for the Voicebox backend
- Build a music composition engine using DSP
- Add support for Hindi text normalization
- Create a dedicated Indic TTS model integration

### 5. Documentation
- Translate documentation to Hindi
- Add more example verses for each Chhand
- Create video tutorials for Vedic recitation
- Add audio examples for each Rāga

---

## Code Style

### HTML/CSS/JS
- Single-file architecture: all code lives in `index.html`
- Use CSS custom properties (variables) for colors and spacing
- Use `'Noto Sans Devanagari'` for all Indic text
- Include both English and Devanāgarī labels on UI elements
- Follow the saffron/gold/dark color palette

### Markdown
- Use IAST transliteration with full diacritics (ā, ī, ū, ṛ, ṅ, ñ, ṭ, ḍ, ṇ, ś, ṣ, ḥ, ṁ)
- Include Devanāgarī alongside IAST where appropriate
- Use tables for structured data
- Reference sources for musical/linguistic claims

### Naming
- Use Sanskrit terms with IAST transliteration
- Provide English translations in parentheses
- Example: "Rāga (राग) — melodic framework"

---

## Getting Started

1. Clone or copy the project directory
2. Start the Voicebox backend (see `README.md`)
3. Open `index.html` in a browser
4. Make changes and test locally

---

## Reporting Issues

When reporting an issue, please include:

1. **What you expected** vs **what happened**
2. **Browser** and **OS** version
3. **Sanskrit text** that triggered the issue (if phonetics-related)
4. **Console errors** (open Developer Tools → Console)
5. **Backend logs** if generation failed

---

## Domain Expertise Welcome

This project especially welcomes contributions from:

- **Sanskrit scholars** — for phonetics accuracy and Vedic recitation rules
- **Indian Classical musicians** — for Rāga/Tāla accuracy
- **Computational linguists** — for Devanāgarī NLP and phonemizer work
- **Audio engineers** — for voice cloning quality improvements

---

> ॐ सह नाववतु सह नौ भुनक्तु सह वीर्यं करवावहै
> *"May we be protected together, may we be nourished together, may we work together with great energy."*
