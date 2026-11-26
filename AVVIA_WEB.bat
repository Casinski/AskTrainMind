@echo off
REM AskTrainMind - PAGINA WEB DBFlotte1000.html
REM Crea (senza eseguire l'OPZIONE 0) la pagina web dal file Excel del DB Flotte presente
REM nella cartella del progetto, la salva in dist\<AAAA-MM-GG>\DBFlotte1000.html insieme
REM alla copia del file Excel e la apre nel browser. Il file Excel non viene modificato.
REM Senza Python apre l'ultima pagina gia' creata (dist\ oppure User\AskTrainMind.html).
cd /d "%~dp0"
chcp 65001 >nul
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if defined PY (
    %PY% -W ignore opzione0.py --web
    if not errorlevel 1 goto :eof
    echo.
    echo  La pagina web non e' stata creata: leggi i messaggi sopra.
    pause
    goto :eof
)
echo  Python non trovato: apro l'ultima pagina gia' creata.
set "LAST="
if exist "dist\" (
    for /f "delims=" %%d in ('dir /b /ad /o-n "dist" 2^>nul') do (
        if not defined LAST if exist "dist\%%d\DBFlotte1000.html" set "LAST=dist\%%d\DBFlotte1000.html"
    )
)
if defined LAST (
    start "" "%LAST%"
    goto :eof
)
if exist "User\AskTrainMind.html" (
    start "" "User\AskTrainMind.html"
    goto :eof
)
echo  Nessuna pagina disponibile: installa Python oppure crea la pagina con AVVIA_DEVELOPER.bat.
pause
