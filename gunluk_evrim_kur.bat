@echo off
REM Registers the daily self-evolution run with Windows Task Scheduler.
REM Runs once a day at 09:00. Re-running this file updates the existing task.
REM Remove it later with:  schtasks /delete /tn "JARVIS Gunluk Evrim" /f

setlocal
set TASK_NAME=JARVIS Gunluk Evrim
set RUNNER=%~dp0gunluk_evrim_calistir.bat

echo Gorev kaydediliyor: %TASK_NAME%
echo Calistirilacak: %RUNNER%
echo.

schtasks /create /tn "%TASK_NAME%" /tr "\"%RUNNER%\"" /sc daily /st 09:00 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo TAMAM - JARVIS her gun saat 09:00'da kendini gelistirecek.
    echo Sonuclar: %~dp0evolution.log
    echo.
    echo Hemen test etmek icin:  schtasks /run /tn "%TASK_NAME%"
) else (
    echo.
    echo HATA - gorev olusturulamadi. Bu dosyayi YONETICI olarak calistirmayi dene.
)

echo.
pause
