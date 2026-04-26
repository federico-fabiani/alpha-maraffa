@echo off
REM RL batch training: N PPO pipeline iterations (default 5) with resume.
REM Progress is saved — re-run to resume after interruption.
REM Report written to game\backend\artifacts\training_rl\rl_batch_report.md
REM
REM Usage:
REM   train_rl_batch.bat               5 iterations (default)
REM   train_rl_batch.bat --n 10        10 iterations
REM   train_rl_batch.bat --reset       clear state and restart
cd /d "%~dp0game\backend" || exit /b 1
uv run python -m aimaraffa.ai.rl_batch %*
exit /b %ERRORLEVEL%
