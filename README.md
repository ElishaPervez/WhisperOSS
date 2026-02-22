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
1.  Run `python src/main.py`.
2.  **First Run**: Enter your Groq API key when prompted.
3.  **Record**: Hold `Ctrl + Win` (default) to record. Release to transcribe.
4.  **Quick Answer Mode**: Hold `Win + Ctrl` to run the short-answer search flow.
5.  **Tray Icon**: The app runs in the background. Check the system tray to access settings.

## ⚙️ Advanced: Antigravity Proxy Search (Optional)
By default, quick-answer search uses **Groq** so the app works out of the box.

If you want to use the optional Antigravity proxy provider:
1.  Open app settings and enable `Advanced > Antigravity Proxy (Search)`.
2.  Install and run Antigravity Manager locally.
3.  Start the local proxy (default `http://127.0.0.1:8045`).
4.  In Antigravity Manager, enable MCP Web Search.
5.  Paste your proxy API key/model values in the Advanced settings fields.

If proxy search fails, the app automatically falls back to Groq search.

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
