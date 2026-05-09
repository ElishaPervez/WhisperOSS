# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = []
hiddenimports = []

for pkg in (
    "PyQt6",
    "keyring",
    "keyboard",
    "sounddevice",
    "pyaudio",
    "groq",
    "google.genai",
    "openai",
    "numpy",
    "pyperclip",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        # Package not installed / not required at build time.
        pass

# Project modules that are imported lazily inside functions; make sure
# PyInstaller sees them.
hiddenimports += collect_submodules("src")

# `keyboard` loads its platform backend lazily; PyInstaller's static
# analysis misses it on Windows.
hiddenimports += ["keyboard._winkeyboard"]

block_cipher = None

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "pytest_qt", "pytest_mock", "pytest_cov"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WhisperOSS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WhisperOSS",
)
