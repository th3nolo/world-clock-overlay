@echo off
setlocal
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo Set up the Windows virtual environment using README.md.
    pause
    exit /b 1
)

start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0clock.py"
