import json
import os
from pathlib import Path
import logging
from src.secret_store import ApiKeyStore

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
    "formatter_model": "openai/gpt-oss-120b",  # Default fast/smart model
    "input_device_index": None, # None means default
    "appearance_mode": "auto",  # auto | dark | light
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
        self._secret_store = ApiKeyStore()
        self._ensure_config_exists()
        self.config = self._load_config()
        self._migrate_plaintext_api_key()

    def _migrate_plaintext_api_key(self):
        """Move legacy plaintext API key from config.json into secure store."""
        plaintext_key = str(self.config.get("api_key", "") or "").strip()
        if not plaintext_key:
            return

        if not self._secret_store.is_available:
            logger.warning("Secure API key storage unavailable; keeping key in config.json.")
            return

        existing_secure_key = self._secret_store.get_api_key()
        if existing_secure_key:
            self.config["api_key"] = ""
            self._save_config(self.config)
            logger.info("Secure credential already present; scrubbed plaintext config fallback.")
            return

        if self._secret_store.set_api_key(plaintext_key):
            self.config["api_key"] = ""
            self._save_config(self.config)
            logger.info("Migrated API key from config.json to secure credential storage.")
        else:
            logger.warning("Failed to migrate API key to secure storage; keeping plaintext fallback.")

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
        if key == "api_key":
            secure_key = self._secret_store.get_api_key()
            if secure_key:
                return secure_key
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a configuration value in memory."""
        if key == "api_key":
            normalized = str(value or "").strip()
            if not normalized:
                self._secret_store.clear_api_key()
                self.config["api_key"] = ""
                return

            if self._secret_store.is_available and self._secret_store.set_api_key(normalized):
                # Keep config file scrubbed when secure storage is active.
                self.config["api_key"] = ""
                return

            logger.warning("Secure API key storage unavailable; falling back to config.json.")
            self.config["api_key"] = normalized
            return

        self.config[key] = value

    def save(self):
        """Persist current configuration to disk."""
        self._save_config(self.config)
