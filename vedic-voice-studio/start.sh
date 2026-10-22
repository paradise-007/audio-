#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Vedic Voice Studio — Start Script
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VOICEBOX_DIR="$(cd "$SCRIPT_DIR/../voicebox" && pwd)"
PYTHON="$VOICEBOX_DIR/backend/venv/bin/python"

echo ""
echo "  🕉️  Vedic Voice Studio · वैदिक स्वर स्टूडियो"
echo "  ═══════════════════════════════════════════════"
echo ""

if [ ! -f "$PYTHON" ]; then
    echo "❌ Voicebox venv not found. Run install.sh first."
    exit 1
fi

# Check if backend is already running
if lsof -i :8000 >/dev/null 2>&1; then
    echo "✅ Backend already running on port 8000"
else
    echo "🚀 Starting Voicebox backend..."
    echo "   Python: $("$PYTHON" --version)"
    echo "   Server: http://127.0.0.1:8000"
    echo ""

    cd "$VOICEBOX_DIR"
    "$PYTHON" -m backend.main &
    BACKEND_PID=$!
    echo "   Backend PID: $BACKEND_PID"

    echo "   Waiting for backend to be ready..."
    for i in $(seq 1 30); do
        if curl -s http://127.0.0.1:8000/health >/dev/null 2>&1; then
            echo "   ✅ Backend ready!"
            break
        fi
        sleep 1
        if [ "$i" -eq 30 ]; then
            echo "   ⚠️  Backend may still be loading. Opening UI anyway..."
        fi
    done
fi

echo ""
echo "🌐 Opening Vedic Voice Studio..."

if command -v open >/dev/null 2>&1; then
    open "$SCRIPT_DIR/index.html"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$SCRIPT_DIR/index.html"
else
    echo "   Open manually: $SCRIPT_DIR/index.html"
fi

echo "═══════════════════════════════════════════════════"
echo "  Press Ctrl+C to stop the backend server"
echo "═══════════════════════════════════════════════════"

if [ -n "$BACKEND_PID" ]; then
    wait "$BACKEND_PID"
fi
