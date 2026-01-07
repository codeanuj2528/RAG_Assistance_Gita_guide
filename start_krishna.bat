@echo off
REM ================================================
REM Krishna Voice Assistant - Quick Start
REM Creates venv, installs requirements, runs server
REM ================================================

echo.
echo ================================================
echo   Krishna Voice Assistant - Quick Start
echo ================================================
echo.

REM Check if venv exists
if not exist "venv" (
    echo [1/4] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv. Make sure Python is installed.
        pause
        exit /b 1
    )
    echo       Done!
) else (
    echo [1/4] Virtual environment already exists. Skipping...
)

echo.
echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat
echo       Done!

echo.
echo [3/4] Installing requirements...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)
echo       Done!

echo.
echo ================================================
echo   All dependencies installed!
echo ================================================
echo.
echo [4/4] Starting Krishna Voice Assistant...
echo.
echo ------------------------------------------------
echo   Open this URL in your browser:
echo   http://localhost:8000/krishna_complete.html
echo ------------------------------------------------
echo.
echo   Press Ctrl+C to stop the server
echo.

python launch.py

pause
