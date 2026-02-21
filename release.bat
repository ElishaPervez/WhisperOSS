@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM WhisperOSS Release XML Generator
REM Generates an XML package of project source files
REM ============================================================

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "OUTDIR=%ROOT%dist\xmls"
set "OUTFILE=%OUTDIR%\whispeross-release.xml"
set "PY_SCRIPT=%ROOT%dist\_release_gen.py"

REM Create output directory
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

echo.
echo ---------------------------------------------------
echo WhisperOSS Release XML Generator
echo ---------------------------------------------------
echo.

REM Avoid bytecode caches during generation
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONWARNINGS=ignore"

echo Cleaning caches ...
for /f "delims=" %%D in ('dir /s /b /ad "__pycache__" 2^>nul') do rmdir /s /q "%%D" 2>nul
for /f "delims=" %%D in ('dir /s /b /ad ".pytest_cache" 2^>nul') do rmdir /s /q "%%D" 2>nul
if exist "%OUTDIR%\*.xml" del /q "%OUTDIR%\*.xml"

REM Check Python script exists
if not exist "%PY_SCRIPT%" (
    echo ERROR: Generator script not found: %PY_SCRIPT%
    goto :fail
)

echo Generating XML package ...
python -B "%PY_SCRIPT%" "." "%OUTFILE%"

if errorlevel 1 goto :fail

echo.
echo ---------------------------------------------------
echo Release Completed Successfully!
echo Output: %OUTFILE%
echo ---------------------------------------------------
echo.
pause
exit /b 0

:fail
echo.
echo ---------------------------------------------------
echo ERROR: Failed to generate release XML!
echo ---------------------------------------------------
pause
exit /b 1
