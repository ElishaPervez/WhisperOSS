import json
import os
from pathlib import Path
import logging

# Setup basic logging if not already configured
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use AppData/Roaming for Windows standard
app_data = os.getenv('APPDATA')
if app_data:
    CONFIG_DIR = Path(app_data) / "WhisperOSS"
else:
    # Fallback for non-Windows or weird envs
    CONFIG_DIR = Path.home() / ".whispeross"

DEFAULT_CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "transcription_model": "whisper-large-v3",
    "formatter_model": "llama3-70b-8192",  # Default fast/smart model
    "input_device_index": None, # None means default
    "use_formatter": False,
    "translation_enabled": False,
    "target_language": "English"
}

class ConfigManager:
    def __init__(self, config_file: Path = None):
        """
        Initialize ConfigManager.
        
        Args:
            config_file (Path, optional): Path to the configuration file. 
                                          Defaults to standard app data location.
        """
        self.config_file = Path(config_file) if config_file else DEFAULT_CONFIG_FILE
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self):
        """Ensure the configuration directory and file exist."""
        try:
            config_dir = self.config_file.parent
            if not config_dir.exists():
                config_dir.mkdir(parents=True, exist_ok=True)
            
            if not self.config_file.exists():
                logger.info(f"Creating default config at {self.config_file}")
                self._save_config(DEFAULT_CONFIG)
        except OSError as e:
            logger.error(f"Failed to ensure config existence: {e}")

    def _load_config(self):
        """Load configuration from file."""
        try:
            if not self.config_file.exists():
                return DEFAULT_CONFIG.copy()

            with open(self.config_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Config file {self.config_file} is corrupt. Using defaults.")
            return DEFAULT_CONFIG.copy()
        except OSError as e:
            logger.error(f"Failed to load config: {e}. Using defaults.")
            return DEFAULT_CONFIG.copy()

    def _save_config(self, config_data):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=4)
        except OSError as e:
            logger.error(f"Failed to save config to {self.config_file}: {e}")

    def get(self, key, default=None):
        """Get a configuration value."""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a configuration value in memory."""
        self.config[key] = value

    def save(self):
        """Persist current configuration to disk."""
        self._save_config(self.config)
