# WhisperOSS

A blazing fast, AI-powered voice typing application for Windows.

## 🚀 Features
- **Deep Integration**: Seamlessly types into any application.
- **Groq LPU Speed**: Leveraging `whisper-large-v3` on Groq Cloud for near-instant transcription.
- **Smart Formatting**: Optionally process text with Llama 3/Mixtral to add punctuation, bullet points, and fix math symbols (e.g., `^2` → `²`).
- **Visualizer**: Real-time RMS audio visualizer.
- **Privacy**: No audio is stored remotely; only transiently processed by Groq API.

## 🛠️ Setup
1.  **Install Python 3.10+**.
2.  **Install Dependencies**:
    ```bash
    pip install PyQt6 groq pyaudio keyboard pyperclip soundfile numpy
    ```
3.  **Get an API Key**: Sign up at [console.groq.com](https://console.groq.com) and create an API Key.

## 🏃 Usage
1.  Run `run.bat` (or `python src/main.py`).
2.  Click **Set API Key** and paste your key.
3.  **Record**: Press `Ctrl+Shift+Space` or click the big Red Button.
4.  **Format Toggle**:
    - **OFF**: Raw, fast transcription.
    - **ON**: AI-formatted text (lists, math symbols, proper casing).

## 📂 Configuration
Your settings (API Key, Mic Device) are saved in `%APPDATA%\WhisperOSS\config.json`.
