import os
from pathlib import Path

# Use AppData/Roaming for Windows standard
app_data = os.getenv('APPDATA')
if app_data:
    CONFIG_DIR = Path(app_data) / "WhisperOSS"
else:
    # Fallback for non-Windows or weird envs
    CONFIG_DIR = Path.home() / ".whispeross"

CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "transcription_model": "whisper-large-v3",
    "formatter_model": "llama3-70b-8192",  # Default fast/smart model
    "input_device_index": None, # None means default
    "use_formatter": False
}

class ConfigManager:
    def __init__(self):
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self):
        if not CONFIG_DIR.exists():
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            self._save_config(DEFAULT_CONFIG)

    def _load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return DEFAULT_CONFIG

    def _save_config(self, config_data):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self._save_config(self.config)
