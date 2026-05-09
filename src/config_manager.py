import json
import os
from pathlib import Path
import logging
from src.secret_store import ApiKeyStore

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
    "gemini_api_key": "",
    "gemini_model": "models/gemma-4-31b-it",
    # "transcription_model" removed — TranscriptionWorker uses whisper-large-v3 directly.
    # Add back here and wire to TranscriptionWorker if model selection is needed in future.
    "formatter_model": "openai/gpt-oss-120b",  # Default fast/smart model
    # Single formatter style mode:
    # retained for backward-compatibility with older configs; only "Default" is used.
    "formatting_style": "Default",
    "input_device_index": None, # None means default
    "appearance_mode": "auto",  # auto | dark | light
    "animation_fps": 100,
    # Streaming answer reveal behavior in the floating visualizer.
    # - stream_realtime_enabled=True: render each arrived update immediately.
    # - stream_reveal_wps: paced reveal speed used when realtime is disabled.
    # - stream_catch_up_enabled=True: dynamically accelerate paced mode when
    #   backlog grows so the UI catches up faster.
    "stream_realtime_enabled": True,
    "stream_reveal_wps": 8,
    "stream_catch_up_enabled": True,
    "use_formatter": False,
    "casual_mode": False,
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
        self._secret_stores = {
            "api_key": ApiKeyStore(account_name="groq_api_key"),
            "gemini_api_key": ApiKeyStore(account_name="gemini_api_key"),
        }
        self._ensure_config_exists()
        self.config = self._load_config()
        self._migrate_plaintext_api_keys()

    def _migrate_plaintext_api_keys(self):
        """Move legacy plaintext API keys from config.json into secure storage."""
        changed = False
        for key_name, store in self._secret_stores.items():
            plaintext_key = str(self.config.get(key_name, "") or "").strip()
            if not plaintext_key:
                continue

            if not store.is_available:
                logger.warning("Secure storage unavailable for %s; keeping key in config.json.", key_name)
                continue

            existing_secure_key = store.get_api_key()
            if existing_secure_key:
                self.config[key_name] = ""
                changed = True
                continue

            if store.set_api_key(plaintext_key):
                self.config[key_name] = ""
                changed = True
                logger.info("Migrated %s from config.json to secure credential storage.", key_name)
            else:
                logger.warning("Failed to migrate %s to secure storage; keeping plaintext fallback.", key_name)

        if changed:
            self._save_config(self.config)

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
        """Load configuration from file, merging any missing keys from DEFAULT_CONFIG."""
        try:
            if not self.config_file.exists():
                return DEFAULT_CONFIG.copy()

            with open(self.config_file, 'r') as f:
                loaded = json.load(f)

            # Forward-migrate: add keys that exist in DEFAULT_CONFIG but are absent
            # from an older config file so callers can always rely on every key existing.
            merged = DEFAULT_CONFIG.copy()
            merged.update(loaded)
            return merged
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
            return True
        except OSError as e:
            logger.error(f"Failed to save config to {self.config_file}: {e}")
            return False

    def get(self, key, default=None):
        """Get a configuration value."""
        store = self._secret_stores.get(key)
        if store is not None:
            secure_key = store.get_api_key()
            if secure_key:
                return secure_key
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a configuration value in memory."""
        store = self._secret_stores.get(key)
        if store is not None:
            normalized = str(value or "").strip()
            if not normalized:
                store.clear_api_key()
                self.config[key] = ""
                return

            if store.is_available and store.set_api_key(normalized):
                # Keep config file scrubbed when secure storage is active.
                self.config[key] = ""
                return

            logger.warning("Secure API key storage unavailable for %s; falling back to config.json.", key)
            self.config[key] = normalized
            return

        self.config[key] = value

    def save(self):
        """Persist current configuration to disk."""
        return self._save_config(self.config)
