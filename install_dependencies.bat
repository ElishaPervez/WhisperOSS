@echo off
echo ========================================
echo   WhisperOSS Dependency Installer
echo ========================================
echo.

echo Installing Python dependencies...
echo.

if exist requirements-lock.txt (
    echo Found requirements-lock.txt, installing pinned versions...
    pip install -r requirements-lock.txt
) else (
    echo requirements-lock.txt not found, installing from requirements.txt...
    pip install -r requirements.txt
)

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo You can now run WhisperOSS using:
echo   - run.bat (minimal console)
echo   - run_silent.vbs (completely invisible)
echo.
pause
