@echo off
setlocal

set "ROOT=%~dp0"
set "VERSION=%~1"
if "%VERSION%"=="" set "VERSION=0.1.0"

echo.
echo ========================================
echo   WhisperOSS Installer Builder
echo ========================================
echo.

powershell -ExecutionPolicy Bypass -File "%ROOT%scripts\build_windows_installer.ps1" -Version "%VERSION%"
if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build succeeded.
pause
exit /b 0
