@echo off
REM Activate virtual environment and run WhisperOSS
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    python -m src.main
) else (
    echo [ERROR] Virtual environment not found.
    echo Please run install_dependencies.bat first.
    pause
)