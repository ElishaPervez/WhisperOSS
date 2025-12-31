import pytest
from src.config_manager import DEFAULT_CONFIG
from src import prompts

def test_translation_config_defaults():
    assert "translation_enabled" in DEFAULT_CONFIG
    assert "target_language" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["translation_enabled"] is False
    assert DEFAULT_CONFIG["target_language"] == "English"

def test_translation_prompt():
    assert hasattr(prompts, "SYSTEM_PROMPT_TRANSLATOR")
    assert "{language}" in prompts.SYSTEM_PROMPT_TRANSLATOR
    assert "format" in prompts.SYSTEM_PROMPT_TRANSLATOR.lower()
    assert "translate" in prompts.SYSTEM_PROMPT_TRANSLATOR.lower()
