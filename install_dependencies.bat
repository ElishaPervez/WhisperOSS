@echo off
echo ========================================
echo   WhisperOSS Dependency Installer
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing Python dependencies...
echo.

pip install --upgrade pip
pip install PyQt6 sounddevice keyboard pyperclip groq numpy

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo You can now run WhisperOSS using:
echo   - run.bat
echo.
pause
