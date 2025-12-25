import pytest
import json
from pathlib import Path
from src.config_manager import ConfigManager, DEFAULT_CONFIG

def test_load_default_config(tmp_path):
    """Test loading defaults when no config file exists."""
    config_dir = tmp_path / "test_config"
    config_file = config_dir / "config.json"
    
    # We expect the ConfigManager to accept a config_file path to be testable
    manager = ConfigManager(config_file=config_file)
    
    assert manager.get("api_key") == ""
    assert manager.get("transcription_model") == "whisper-large-v3"
    assert config_file.exists()

def test_save_and_load_config(tmp_path):
    """Test saving values and reloading them."""
    config_dir = tmp_path / "test_config"
    config_file = config_dir / "config.json"
    
    manager = ConfigManager(config_file=config_file)
    manager.set("api_key", "secret_key")
    
    # Reload from disk
    new_manager = ConfigManager(config_file=config_file)
    assert new_manager.get("api_key") == "secret_key"

def test_corrupt_config_file(tmp_path):
    """Test handling of corrupt config file."""
    config_dir = tmp_path / "test_config"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text("{corrupt_json: ...")
    
    manager = ConfigManager(config_file=config_file)
    # Should fallback to defaults or handle gracefully
    assert manager.get("transcription_model") == "whisper-large-v3"
