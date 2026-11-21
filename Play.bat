@echo off
rem Double-click to play. The first run sets things up, which takes a minute.
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo First run: setting up the game. This only happens once...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if not exist ".venv\Scripts\pythonw.exe" (
        echo.
        echo Could not find Python. Install it from https://www.python.org/downloads/
        echo and tick "Add python.exe to PATH" during setup, then try again.
        pause
        exit /b 1
    )
)

rem Install or update libraries whenever requirements.txt changes.
fc /b requirements.txt ".venv\installed.txt" >nul 2>&1
if errorlevel 1 (
    echo Installing game libraries...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Installing failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
    copy /y requirements.txt ".venv\installed.txt" >nul
)

rem pythonw runs the game without a terminal window.
start "" ".venv\Scripts\pythonw.exe" main.py
