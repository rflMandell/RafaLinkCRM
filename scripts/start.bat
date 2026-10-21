@echo off
cd /d %~dp0..\backend
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
pip install -q -r requirements.txt
echo.
echo RafaLink rodando em http://localhost:8000/login.html
echo.
python -m uvicorn app.main:app --reload --port 8000