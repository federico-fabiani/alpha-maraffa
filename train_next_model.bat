@echo off
REM Iterazione completa: dataset -> train -> analyze -> tournament -> promote.
REM Tutte le manopole stanno in src\aimaraffa\ai\config.py.
cd /d "%~dp0game\backend" || exit /b 1
call uv run python -m aimaraffa.ai
exit /b %ERRORLEVEL%
