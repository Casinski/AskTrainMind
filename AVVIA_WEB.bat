@echo off
REM Avvia l'interfaccia web di AskTrainMind (http://127.0.0.1:8765/)
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 asktrainmind_web.py %*
) else (
    python asktrainmind_web.py %*
)
if errorlevel 1 pause
