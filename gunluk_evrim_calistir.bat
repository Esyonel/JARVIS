@echo off
REM Runs the daily self-evolution cycle. Invoked by Windows Task Scheduler
REM (see gunluk_evrim_kur.bat), or double-click to run it once by hand.
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" daily_evolution.py
