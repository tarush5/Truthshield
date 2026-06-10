@echo off
echo ===================================================
echo           Starting TruthShield System
echo ===================================================

cd /d "%~dp0"

echo Starting ML Backend (Port 8000)...
start "TruthShield ML Backend" cmd /k "cd backend && pip install -r requirements.txt && python -m uvicorn main:app --reload --port 8000"

echo Starting React Frontend (Port 5173)...
start "TruthShield React Frontend" cmd /k "cd frontend && npm install && npm run dev"

echo Starting WhatsApp Bot (Integration)...
start "TruthShield WhatsApp Bot" cmd /k "set PYTHONPATH=%~dp0 && python integrations\whatsapp_bot.py"

echo.
echo All services are starting in separate windows.
echo - ML Backend: http://localhost:8000
echo - React Frontend: http://localhost:5173
echo.
pause
