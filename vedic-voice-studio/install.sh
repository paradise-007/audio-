#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Vedic Voice Studio — Dependency Installer
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VOICEBOX_DIR="$(cd "$SCRIPT_DIR/../voicebox" && pwd)"
VENV="$VOICEBOX_DIR/backend/venv"
PIP="$VENV/bin/pip"
PYTHON="$VENV/bin/python"

echo "═══════════════════════════════════════════════════"
echo "  🕉️  Vedic Voice Studio — Dependency Installer"
echo "═══════════════════════════════════════════════════"
echo ""

if [ ! -f "$PYTHON" ]; then
    echo "❌ Voicebox venv not found at: $VENV"
    exit 1
fi

echo "✅ Found Voicebox venv: $VENV"
echo "   Python: $("$PYTHON" --version)"
echo ""

echo "📦 Installing Indic text processing libraries..."
"$PIP" install --quiet indic-transliteration 2>&1 | tail -1
echo "   ✅ indic-transliteration"

echo ""
echo "📦 Installing IndicF5 dependencies..."
"$PIP" install --quiet f5-tts soundfile librosa 2>&1 | tail -3
echo "   ✅ f5-tts"

echo ""
echo "📦 Installing XTTS v2 (Coqui TTS)..."
"$PIP" install --quiet coqui-tts 2>&1 | tail -3
echo "   ✅ coqui-tts"

echo ""
echo "🔍 Verifying installations..."
"$PYTHON" -c "
errors = []
try:
    from indic_transliteration import sanscript
    print('   ✅ indic-transliteration')
except ImportError as e:
    errors.append(str(e)); print(f'   ❌ indic-transliteration: {e}')
try:
    import f5_tts
    print('   ✅ f5-tts')
except ImportError as e:
    errors.append(str(e)); print(f'   ❌ f5-tts: {e}')
try:
    from transformers import AutoModel
    print('   ✅ transformers')
except ImportError as e:
    errors.append(str(e)); print(f'   ❌ transformers: {e}')
try:
    from TTS.api import TTS
    print('   ✅ coqui-tts')
except ImportError as e:
    errors.append(str(e)); print(f'   ❌ coqui-tts: {e}')
try:
    import torch
    cuda = torch.cuda.is_available()
    mps = torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False
    device = 'CUDA' if cuda else ('MPS' if mps else 'CPU')
    print(f'   ✅ PyTorch {torch.__version__} ({device})')
except ImportError as e:
    errors.append(str(e)); print(f'   ❌ torch: {e}')
if errors:
    print(f'\n⚠️  {len(errors)} package(s) failed.')
else:
    print('\n✅ All packages OK!')
"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ Done! Run:  bash start.sh"
echo "═══════════════════════════════════════════════════"
