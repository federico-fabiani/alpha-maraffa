@echo off
REM Behavioural-cloning pre-trainer: imitates heuristic, saves rl_v0.
REM Run ONCE before train_rl_batch.bat to give PPO a competent warm-start.
REM
REM Usage:
REM   train_rl_bc.bat                          default (10000 eps, 10 epochs)
REM   train_rl_bc.bat --episodes 20000         more data
REM   train_rl_bc.bat --epochs 15              more training passes
REM   train_rl_bc.bat --device cpu             force CPU
cd /d "%~dp0game\backend" || exit /b 1
uv run python -m aimaraffa.ai.rl_bc %*
exit /b %ERRORLEVEL%
