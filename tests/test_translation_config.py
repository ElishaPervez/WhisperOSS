import pytest
from src.config_manager import ConfigManager, DEFAULT_CONFIG
from src import prompts

def test_translation_config_keys():
    """Verify that translation configuration keys exist in DEFAULT_CONFIG."""
    assert "translation_enabled" in DEFAULT_CONFIG
    assert "target_language" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["translation_enabled"] is False
    assert DEFAULT_CONFIG["target_language"] == "English"

def test_translator_prompt_exists():
    """Verify that the translation system prompt is defined."""
    assert hasattr(prompts, "SYSTEM_PROMPT_TRANSLATOR")
    assert "translate" in prompts.SYSTEM_PROMPT_TRANSLATOR.lower()
