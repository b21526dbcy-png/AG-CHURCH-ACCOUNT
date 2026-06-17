@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\flask.exe" (
    echo Flask launcher was not found.
    echo Expected: %cd%\.venv\Scripts\flask.exe
    echo.
    pause
    exit /b 1
)

start "Account Web Server" /D "%cd%" cmd /k ".venv\Scripts\flask.exe --app app run --host 127.0.0.1 --port 5000"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5000"
