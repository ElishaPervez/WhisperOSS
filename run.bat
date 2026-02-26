@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "VENV_PYW=%ROOT%.venv\Scripts\pythonw.exe"

if not exist "%VENV_PY%" (
    echo [ERROR] Windows virtual environment not found:
    echo   "%VENV_PY%"
    if exist "%ROOT%.venv\bin\python" (
        echo.
        echo Found a Linux/WSL virtual environment at ".venv\\bin\\python".
        echo Re-run install_dependencies.bat from Windows CMD/PowerShell
        echo to create ".venv\\Scripts\\python.exe".
    ) else (
        echo Run install_dependencies.bat first.
    )
    pause
    exit /b 1
)

if /i "%~1"=="--background" (
    if not exist "%VENV_PYW%" (
        echo [ERROR] Background mode requires:
        echo   "%VENV_PYW%"
        pause
        exit /b 1
    )
    start "" "%VENV_PYW%" "%ROOT%src\main.py"
    exit /b 0
)

echo Starting WhisperOSS...
"%VENV_PY%" "%ROOT%src\main.py"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] WhisperOSS exited with code %EXIT_CODE%.
    echo Review the error output above.
    pause
)
exit /b %EXIT_CODE%
