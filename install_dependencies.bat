@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "VENV_DIR=%ROOT%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo ========================================
echo   WhisperOSS Dependency Installer
echo ========================================
echo.

if exist "%VENV_PY%" (
    echo Found virtual environment: "%VENV_DIR%"
) else (
    echo Creating virtual environment: "%VENV_DIR%"
    py -3 -m venv "%VENV_DIR%" >nul 2>&1
    if errorlevel 1 (
        python -m venv "%VENV_DIR%"
    )
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to create virtual environment.
        echo Make sure Python 3 is installed and on PATH.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Upgrading pip in virtual environment...
"%VENV_PY%" -m pip install --upgrade pip >nul
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip in virtual environment.
    pause
    exit /b 1
)

if exist requirements-lock.txt (
    set "REQ_FILE=requirements-lock.txt"
) else (
    set "REQ_FILE=requirements.txt"
)

echo.
echo Installing dependencies from %REQ_FILE%...
"%VENV_PY%" -m pip install -r "%REQ_FILE%"
if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Virtual environment:
echo   %VENV_DIR%
echo.
echo You can now run WhisperOSS using:
echo   - run.bat
echo.
pause
