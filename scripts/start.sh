#!/usr/bin/env bash
cd "$(dirname "$0")/../backend"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
echo
echo "RafaLink rodando em http://localhost:8000/login.html"
echo
python -m uvicorn app.main:app --reload --port 8000