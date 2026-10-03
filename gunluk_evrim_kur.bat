@echo off
REM Registers the self-evolution run with Windows Task Scheduler, 3x a day:
REM   09:00 Python, 14:00 3D design/printing, 20:00 free choice
REM (daily_evolution.py picks the topic from the hour).
REM Re-running this file updates the existing tasks.
REM Remove them later with:
REM   schtasks /delete /tn "JARVIS Evrim 09" /f
REM   schtasks /delete /tn "JARVIS Evrim 14" /f
REM   schtasks /delete /tn "JARVIS Evrim 20" /f

setlocal
set RUNNER=%~dp0gunluk_evrim_calistir.bat
set FAILED=0

echo Calistirilacak: %RUNNER%
echo.

REM Old single 02:00 task, replaced by the three below.
schtasks /delete /tn "JARVIS Gunluk Evrim" /f >nul 2>&1

for %%H in (09 14 20) do (
    schtasks /create /tn "JARVIS Evrim %%H" /tr "\"%RUNNER%\"" /sc daily /st %%H:00 /f
    if errorlevel 1 set FAILED=1
)

if %FAILED% EQU 0 (
    echo.
    echo TAMAM - JARVIS her gun 09:00, 14:00 ve 20:00'de kendini gelistirecek.
    echo Sonuclar: %~dp0evolution.log
    echo.
    echo Hemen test etmek icin:  schtasks /run /tn "JARVIS Evrim 09"
) else (
    echo.
    echo HATA - gorev olusturulamadi. Bu dosyayi YONETICI olarak calistirmayi dene.
)

echo.
pause
