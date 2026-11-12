@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo == Installazione server MCP "stampante" ==
where python >nul 2>&1 || (echo Python non trovato: installalo da https://www.python.org spuntando "Add python.exe to PATH". & pause & exit /b 1)
python -m pip install --upgrade -r requirements.txt || (echo Errore installando le dipendenze. & pause & exit /b 1)
echo.
echo Stampanti trovate:
powershell -NoProfile -Command "Get-CimInstance Win32_Printer | ForEach-Object { $_.Name + $(if ($_.Default) {'  (predefinita)'} else {''}) }"
echo.
if exist "%LOCALAPPDATA%\SumatraPDF\SumatraPDF.exe" (echo SumatraPDF: trovato) else if exist "C:\Program Files\SumatraPDF\SumatraPDF.exe" (echo SumatraPDF: trovato) else (echo SumatraPDF NON trovato: consigliato per stampare i PDF - https://www.sumatrapdfreader.org)
echo.
echo Fatto. Ora avvia "avvia-da-telefono.bat".
pause
