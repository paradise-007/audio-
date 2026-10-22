# Chhandas Reference Guide — छन्दः संदर्भ

A comprehensive reference for Sanskrit prosody (Chandas) as used in Vedic Voice Studio.

---

## What is Chhandas?

**Chhandas** (छन्दः) is the science of Sanskrit poetic meters. It governs the rhythmic structure of verses by defining:

- **Pāda** (पाद) — A quarter-verse or metrical foot
- **Akṣara** (अक्षर) — Syllable count per pāda
- **Laghu** (लघु, ⏑) — Light syllable (1 mātrā)
- **Guru** (गुरु, —) — Heavy syllable (2 mātrās)
- **Yati** (यति) — Caesura/pause point within a pāda

### Syllable Weight Rules

A syllable is **Guru** (heavy, —) if:
1. It contains a long vowel (ā, ī, ū, ṝ, e, ai, o, au)
2. It contains a short vowel followed by a conjunct consonant (saṁyogādya)
3. It contains a short vowel followed by visarga (ḥ) or anusvāra (ṁ)
4. It is the last syllable of a pāda (by convention in some meters)

A syllable is **Laghu** (light, ⏑) if:
1. It contains a short vowel (a, i, u, ṛ, ḷ) not followed by a conjunct

---

## Gaṇa System (Syllable Groups)

Classical meters use groups of 3 syllables called **Gaṇa** (गण):

| Gaṇa | Pattern | Mnemonic | Example |
|------|---------|----------|---------|
| **ya** (य) | ⏑ — — | ya-mā-tā | yamātā |
| **ma** (म) | — — — | mā-tā-rā | mātārā |
| **ta** (त) | — — ⏑ | tā-rā-ja | tārāja |
| **ra** (र) | — ⏑ — | rā-ja-bhā | rājabhā |
| **ja** (ज) | ⏑ — ⏑ | ja-bhā-na | jabhāna |
| **bha** (भ) | — ⏑ ⏑ | bhā-na-sa | bhānasa |
| **na** (न) | ⏑ ⏑ ⏑ | na-sa-la | nasala |
| **sa** (स) | ⏑ ⏑ — | sa-la-gā | salagā |

**Mnemonic verse**: यमाताराजभानसलगा (yamātārājabhānasalagā)

---

## Supported Meters

### 1. Gāyatrī · गायत्री

| Property | Value |
|----------|-------|
| **Syllables per pāda** | 8 |
| **Number of pādas** | 3 |
| **Total syllables** | 24 |
| **Pattern** | Free (no fixed laghu/guru pattern) |
| **Yati** | After each pāda (every 8 syllables) |
| **Origin** | Ṛg Veda |
| **Famous example** | Gāyatrī Mantra |

**Example:**
```
tat sa vi tur  va re ṇyaṁ  |    (pāda 1: 8 syllables)
bhar go  de va sya  dhī ma hi |  (pāda 2: 8 syllables)
dhi yo  yo  naḥ pra co da yāt | (pāda 3: 8 syllables)
```

---

### 2. Anuṣṭubh / Śloka · अनुष्टुभ्

| Property | Value |
|----------|-------|
| **Syllables per pāda** | 8 |
| **Number of pādas** | 4 |
| **Total syllables** | 32 |
| **Pattern** | 5th syllable is laghu, 6th is guru, 7th alternates |
| **Yati** | After every 8 syllables (at pāda end) |
| **Origin** | Classical Sanskrit |
| **Famous example** | Bhagavad Gītā verses |

**Śloka pattern (odd pādas):** × × × × ⏑ — — ×
**Śloka pattern (even pādas):** × × × × ⏑ — ⏑ ×

**Example (BG 2.47):**
```
kar ma ṇy e  vā dhi kā ra ste |  (pāda 1)
mā pha le ṣu  ka dā ca na   |  (pāda 2)
mā kar ma pha la  he tur bhūr |  (pāda 3)
mā te  saṅ go' stv a kar ma ṇi |  (pāda 4)
```

---

### 3. Triṣṭubh · त्रिष्टुभ्

| Property | Value |
|----------|-------|
| **Syllables per pāda** | 11 |
| **Number of pādas** | 4 |
| **Total syllables** | 44 |
| **Pattern** | ⏑ — ⏑ — × — ⏑ — ⏑ — × |
| **Yati** | After syllable 5 within each pāda, and at pāda end |
| **Origin** | Ṛg Veda |
| **Famous example** | Many Ṛg Vedic hymns |

**Structure:**
```
pāda: [1-5] yati [6-11]
      11 syllables total
```

---

### 4. Jagatī · जगती

| Property | Value |
|----------|-------|
| **Syllables per pāda** | 12 |
| **Number of pādas** | 4 |
| **Total syllables** | 48 |
| **Pattern** | Varies by sub-meter |
| **Yati** | After syllable 6 within each pāda |
| **Origin** | Ṛg Veda |

---

### 5. Mālinī · मालिनी

| Property | Value |
|----------|-------|
| **Syllables per pāda** | 15 |
| **Number of pādas** | 4 |
| **Total syllables** | 60 |
| **Gaṇa pattern** | na na ma ya ya |
| **Pattern** | ⏑ ⏑ ⏑ ⏑ ⏑ ⏑ — — — ⏑ — — ⏑ — — |
| **Yati** | After syllable 8 |
| **Famous example** | Meghadūta stanzas |

---

### 6. Vasantatilakā · वसन्ततिलका

| Property | Value |
|----------|-------|
| **Syllables per pāda** | 14 |
| **Number of pādas** | 4 |
| **Total syllables** | 56 |
| **Gaṇa pattern** | ta bha ja ja ga ga |
| **Pattern** | — — ⏑ — ⏑ ⏑ ⏑ — ⏑ ⏑ ⏑ — — — |
| **Yati** | After syllable 8 |
| **Famous example** | Uttararāmacarita stanzas |

---

### 7. Śārdūlavikrīḍita · शार्दूलविक्रीडित

| Property | Value |
|----------|-------|
| **Syllables per pāda** | 19 |
| **Number of pādas** | 4 |
| **Total syllables** | 76 |
| **Gaṇa pattern** | ma sa ja sa ta ta ga |
| **Pattern** | — — — ⏑ ⏑ — ⏑ — ⏑ ⏑ ⏑ — — — ⏑ — — ⏑ — |
| **Yati** | After syllables 12 and 7 |
| **Famous example** | Subhāṣita verses |

---

### 8. Mandākrāntā · मन्दाक्रान्ता

| Property | Value |
|----------|-------|
| **Syllables per pāda** | 17 |
| **Number of pādas** | 4 |
| **Total syllables** | 68 |
| **Gaṇa pattern** | ma bha na ta ta ga ga |
| **Pattern** | — — — — ⏑ ⏑ ⏑ ⏑ ⏑ — — — ⏑ — — ⏑ — |
| **Yati** | After syllables 4 and 10 |
| **Famous example** | Meghadūta of Kālidāsa |

---

### 9. Free / Prose · गद्य

| Property | Value |
|----------|-------|
| **Syllables per pāda** | Variable |
| **Number of pādas** | Variable |
| **Pattern** | None (prose) |
| **Usage** | Modern Hindi lyrics, free-form Sanskrit compositions |

---

## Meter Identification Algorithm

To identify the meter of a given verse:

1. Count syllables per line/pāda
2. Mark each syllable as laghu (⏑) or guru (—)
3. Match against known patterns:

| Syllables per pāda | Possible Meter |
|-------------------|---------------|
| 8 | Anuṣṭubh / Gāyatrī |
| 11 | Triṣṭubh |
| 12 | Jagatī |
| 14 | Vasantatilakā |
| 15 | Mālinī |
| 17 | Mandākrāntā |
| 19 | Śārdūlavikrīḍita |

---

## Recitation Rules

### Yati (Caesura)
- Take a clean breath at each yati point
- Never break a word across a yati
- Hold for approximately 1 mātrā of silence

### Pāda Boundaries
- Full breath pause (2 mātrās) between pādas
- Verse boundary: 3–4 mātrās of silence

### Virāma (Final Stop)
- The last syllable of a verse may be treated as guru regardless of vowel length
- This is called **pādānta-guru** (end-of-foot heaviness)
