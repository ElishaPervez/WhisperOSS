@echo off
echo ========================================
echo   WhisperOSS Dependency Installer
echo ========================================
echo.

echo Installing Python dependencies...
echo.

pip install PyQt6 pyaudio keyboard pyperclip groq numpy

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
