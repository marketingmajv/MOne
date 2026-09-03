#!/bin/bash
# M-One: Iniciar servidor local + Túnel Cloudflare para testes online

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Criando ambiente virtual .venv..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# Matar processos anteriores na porta 5001 se existirem
lsof -ti :5001 | xargs kill -9 2>/dev/null || true
pkill -f "cloudflared tunnel --url http://localhost:5001" 2>/dev/null || true

echo "Iniciando M-One na porta 5001..."
PORT=5001 python3 app.py &
APP_PID=$!

trap "kill $APP_PID 2>/dev/null; exit" INT TERM EXIT

sleep 2

echo "Iniciando túnel Cloudflare online..."
cloudflared tunnel --url http://localhost:5001
