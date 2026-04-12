@echo off
echo === Marafone Digital ===
echo.

:: Backend
echo [1/2] Avvio backend (FastAPI + uv)...
cd /d "%~dp0game\backend"

uv sync
start "Marafone Backend" cmd /k "uv run uvicorn aimaraffa.api:app --reload --port 8000"
echo Backend avviato su http://localhost:8000
echo.

:: Frontend
echo [2/2] Avvio frontend (React/Vite)...
cd /d "%~dp0game\frontend"

if not exist "node_modules" (
    echo Installo dipendenze npm...
    npm install
)

start "Marafone Frontend" cmd /k "npm run dev"
echo Frontend avviato su http://localhost:5173
echo.

echo === Tutto avviato! Apri http://localhost:5173 nel browser ===
pause
