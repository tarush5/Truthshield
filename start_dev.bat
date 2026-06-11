@echo off
echo ===================================================
echo   TruthShield — Local Development
echo ===================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.11 from https://python.org
    pause
    exit /b 1
)

REM Start Backend
echo [1/2] Starting Backend on http://127.0.0.1:8000 ...
echo       Swagger docs: http://127.0.0.1:8000/docs
echo.
start "TruthShield Backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

REM Wait for backend to be ready
echo       Waiting for backend to start...
timeout /t 5 /nobreak >nul

REM Start Frontend
echo [2/2] Starting Frontend on http://localhost:5173 ...
echo.
start "TruthShield Frontend" cmd /k "cd /d %~dp0\frontend && npm run dev"

echo.
echo ===================================================
echo   Both services started!
echo.
echo   Frontend: http://localhost:5173
echo   Backend:  http://127.0.0.1:8000
echo   API Docs: http://127.0.0.1:8000/docs
echo ===================================================
echo.
echo Press any key to exit (services will keep running)...
pause >nul
