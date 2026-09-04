#!/bin/bash
# M-One: Iniciar servidor local de desenvolvimento

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

# Liberar porta 5001 se estiver em uso
lsof -ti :5001 | xargs kill -9 2>/dev/null || true

echo "Iniciando M-One na porta 5001..."
echo "Acesse localmente em: http://localhost:5001"
echo "Produção oficial em:  https://m-one.majmobilidade.com.br"
echo ""

PORT=5001 python3 app.py
