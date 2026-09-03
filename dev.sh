#!/usr/bin/env bash
set -e
export PORT=${PORT:-5001}
echo "🚀 Iniciando M-One (MAJ Operating System) no ambiente local..."
echo "📍 Porta: ${PORT}"
echo "🌐 Link local: http://localhost:${PORT}"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

exec python app.py
