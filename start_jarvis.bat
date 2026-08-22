@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
start "" /min "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
