import json
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

from src.config_manager import ConfigManager


class FakeSecureStore:
    def __init__(self, available=True):
        self.is_available = available
        self._value = ""

    def get_api_key(self):
        return self._value

    def set_api_key(self, api_key):
        if not self.is_available:
            return False
        self._value = api_key
        return True

    def clear_api_key(self):
        self._value = ""
        return True


def _new_test_config_file() -> Path:
    root = Path(".tmp") / "config_tests" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root / "config.json"


def _cleanup_test_config_file(config_file: Path) -> None:
    test_dir = config_file.parent
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


def test_load_default_config():
    """Test loading defaults when no config file exists."""
    config_file = _new_test_config_file()

    fake_store = FakeSecureStore(available=True)
    with patch("src.config_manager.ApiKeyStore", return_value=fake_store):
        manager = ConfigManager(config_file=config_file)

    assert manager.get("api_key") == ""
    assert manager.get("appearance_mode") == "auto"
    assert config_file.exists()
    _cleanup_test_config_file(config_file)


def test_secure_storage_set_scrubs_config_file():
    """API key should live in secure store and not remain plaintext on disk."""
    config_file = _new_test_config_file()

    fake_store = FakeSecureStore(available=True)
    with patch("src.config_manager.ApiKeyStore", return_value=fake_store):
        manager = ConfigManager(config_file=config_file)
        manager.set("api_key", "secret_key")
        manager.save()

    disk_data = json.loads(config_file.read_text(encoding="utf-8"))
    assert disk_data.get("api_key", "") == ""

    with patch("src.config_manager.ApiKeyStore", return_value=fake_store):
        new_manager = ConfigManager(config_file=config_file)
    assert new_manager.get("api_key") == "secret_key"
    _cleanup_test_config_file(config_file)


def test_migrate_plaintext_api_key_to_secure_store():
    """Legacy plaintext key should be migrated into secure storage on startup."""
    config_file = _new_test_config_file()
    config_file.write_text(
        json.dumps(
            {
                "api_key": "legacy_plaintext",
                "transcription_model": "whisper-large-v3",
            }
        ),
        encoding="utf-8",
    )

    fake_store = FakeSecureStore(available=True)
    with patch("src.config_manager.ApiKeyStore", return_value=fake_store):
        manager = ConfigManager(config_file=config_file)

    assert manager.get("api_key") == "legacy_plaintext"
    disk_data = json.loads(config_file.read_text(encoding="utf-8"))
    assert disk_data.get("api_key", "") == ""
    _cleanup_test_config_file(config_file)


def test_plaintext_fallback_when_secure_store_unavailable():
    """Fallback to config.json when secure backend is unavailable."""
    config_file = _new_test_config_file()

    fake_store = FakeSecureStore(available=False)
    with patch("src.config_manager.ApiKeyStore", return_value=fake_store):
        manager = ConfigManager(config_file=config_file)
        manager.set("api_key", "secret_key")
        manager.save()

    disk_data = json.loads(config_file.read_text(encoding="utf-8"))
    assert disk_data.get("api_key") == "secret_key"

    with patch("src.config_manager.ApiKeyStore", return_value=fake_store):
        new_manager = ConfigManager(config_file=config_file)
    assert new_manager.get("api_key") == "secret_key"
    _cleanup_test_config_file(config_file)
