param(
    [string]$Version = "0.1.0",
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$mainScript = Join-Path $repoRoot "src\main.py"
$innoScript = Join-Path $repoRoot "packaging\windows\WhisperOSS.iss"

Write-Host ""
Write-Host "========================================"
Write-Host "WhisperOSS Desktop Build"
Write-Host "========================================"
Write-Host "Version: $Version"
Write-Host ""

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    throw "Python was not found in PATH."
}

if (-not (Test-Path $mainScript)) {
    throw "Main entry script not found: $mainScript"
}

Write-Host "[1/2] Building app bundle with PyInstaller..."

$pyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", "WhisperOSS",
    "--paths", $repoRoot,
    $mainScript
)

& python @pyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

if ($SkipInstaller) {
    Write-Host "Skipped installer generation as requested (-SkipInstaller)."
    exit 0
}

Write-Host "[2/2] Building installer with Inno Setup..."

if (-not (Test-Path $innoScript)) {
    throw "Inno Setup script not found: $innoScript"
}

$isccCmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
if (-not $isccCmd) {
    $defaultIscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\iscc.exe"
    if (Test-Path $defaultIscc) {
        $isccCmd = @{ Path = $defaultIscc }
    }
}

if (-not $isccCmd) {
    throw "Inno Setup Compiler (iscc.exe) not found. Install Inno Setup 6 and add iscc.exe to PATH."
}

& $isccCmd.Path "/DAppVersion=$Version" $innoScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed."
}

Write-Host ""
Write-Host "Build completed successfully."
Write-Host "- App bundle: dist\\WhisperOSS"
Write-Host "- Installer: dist\\installer"
Write-Host ""
