#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo ""
echo "⚡ LeadHunter Pro — Backend"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verificar Python
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 não encontrado."; exit 1
fi

# Instalar dependências
echo "📦 Instalando dependências..."
pip install -r requirements.txt -q

echo ""
echo "✅ Backend iniciado em http://localhost:5000"
echo "   Deixe este terminal aberto."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 server.py
