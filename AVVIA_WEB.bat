@echo off
REM AskTrainMind - pagina per gli UTENTI: si apre nel browser, nessuna installazione richiesta.
REM (La pagina e' User\AskTrainMind.html: si puo' aprire anche con doppio click.)
cd /d "%~dp0"
if exist "User\AskTrainMind.html" (
    start "" "User\AskTrainMind.html"
) else (
    echo La pagina User\AskTrainMind.html non esiste ancora.
    echo Il developer deve generarla con AVVIA_DEVELOPER.bat, voce 13.
    pause
)
