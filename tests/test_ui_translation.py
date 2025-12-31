import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from unittest.mock import MagicMock
from src.ui_main_window import MainWindow

@pytest.fixture
def mock_config():
    config = MagicMock()
    # Mocking get to return predictable values
    config.get.side_effect = lambda key, default=None: {
        "api_key": "test_key",
        "use_formatter": True, # Keep formatter on by default for these tests
        "input_device_index": 0,
        "formatter_model": "test_model",
        "translation_enabled": False,
        "target_language": "Spanish"
    }.get(key, default)
    return config

@pytest.fixture
def app(qtbot):
    return QApplication.instance() or QApplication([])

def test_translation_ui_elements(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    assert hasattr(window, "translation_toggle")
    assert hasattr(window, "language_input")
    assert hasattr(window, "save_btn")
    
    assert window.translation_toggle.isChecked() is False
    assert window.language_input.text() == "Spanish"

def test_translation_dependency_on_formatter(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    # 1. Turn off AI Formatting
    window.format_toggle.setChecked(False)
    
    # 2. Check if Translation is disabled and unchecked
    assert window.translation_toggle.isEnabled() is False
    assert window.translation_toggle.isChecked() is False
    # Verify session config updated
    mock_config.set.assert_any_call("translation_enabled", False)
    
    # 3. Turn on AI Formatting
    window.format_toggle.setChecked(True)
    assert window.translation_toggle.isEnabled() is True

def test_save_settings_logic(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    # Change values in UI
    window.translation_toggle.setChecked(True)
    window.language_input.setText("Urdu")
    
    # Verify session config updated immediately
    mock_config.set.assert_any_call("translation_enabled", True)
    mock_config.set.assert_any_call("target_language", "Urdu")
    
    # Verify NO save call yet
    mock_config.save.assert_not_called()
    
    # Click SAVE
    qtbot.mouseClick(window.save_btn, Qt.MouseButton.LeftButton)
    
    # Verify disk save called
    mock_config.save.assert_called_once()
