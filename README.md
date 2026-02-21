# WhisperOSS

A blazing fast, AI-powered voice typing application for Windows that feels native.

## 🚀 Features
- **Zero-Latency Recording**: Records directly to RAM (no disk I/O) for instant processing.
- **Groq LPU Speed**: Leverages `whisper-large-v3` on Groq Cloud for near-instant transcription.
- **Ghost Paste**: Intelligently preserves your clipboard while typing into any application.
- **Context Awareness**: Detects the active window (e.g., VS Code vs. Slack) to adjust formatting automatically.
- **Smart Formatting**: 
  - **Styles**: Choose between Casual, Professional Email, Google Docs, or Default.
  - **Symbols**: Auto-converts "squared" -> ², "degrees" -> °, etc.
- **Visualizer**: Beautiful, native Windows-style audio visualizer that follows your cursor.
- **Global Hotkeys**: Hold `Ctrl + Win` (or customize) to record from anywhere.

## 🛠️ Setup
1.  **Install Python 3.10+**.
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Get an API Key**: Sign up at [console.groq.com](https://console.groq.com) and create an API Key.

## 🏃 Usage
1.  Run `run.bat` (or `python src/main.py`).
2.  **First Run**: Enter your Groq API key when prompted.
3.  **Record**: Hold `Ctrl + Win` (default) to record. Release to transcribe.
4.  **Tray Icon**: The app runs in the background. Check the system tray to access settings.

## 🖥️ Desktop Build + Installer (Windows)
WhisperOSS is a native `PyQt6` desktop app. To create an installable Windows package:

1. Install build tools:
   ```bash
   pip install pyinstaller
   ```
2. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) and ensure `iscc.exe` is available in `PATH`.
3. Build app bundle + installer:
   ```bash
   build_installer.bat 0.1.0
   ```

Outputs:
- App bundle: `dist/WhisperOSS/`
- Installer: `dist/installer/WhisperOSS-Setup-<version>.exe`

## 📂 Configuration
Your settings (API Key, Mic Device, Formatting preferences) are saved in `%APPDATA%\WhisperOSS\config.json`.

Security note:
- API keys are stored in OS secure credential storage (Windows Credential Manager via `keyring`) when available.
- Legacy plaintext keys in `config.json` are auto-migrated on startup.

## 🧪 Development
Run the full test suite (now 100% passing) with:
```bash
python -m pytest
```
