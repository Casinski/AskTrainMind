@echo off
REM AskTrainMind - TERMINALE DEVELOPER: analisi, addestramento AI, CONFIG, aggiornamento della cartella User.
cd /d "%~dp0"
chcp 65001 >nul
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 asktrainmind_dev.py %*
) else (
    python asktrainmind_dev.py %*
)
if errorlevel 1 pause
