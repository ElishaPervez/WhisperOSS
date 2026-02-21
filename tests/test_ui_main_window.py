import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from unittest.mock import MagicMock
from src.ui_main_window import MainWindow, AnimatedToggle

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: {
        "api_key": "test_key",
        "use_formatter": False,
        "input_device_index": 0,
        "formatter_model": "test_model"
    }.get(key, default)
    return config

@pytest.fixture
def app(qtbot):
    return QApplication.instance() or QApplication([])

def test_init(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    assert window.windowTitle() == "WhisperOSS Settings"
    assert window.format_toggle.isChecked() is False

def test_api_key_actions_are_separate_buttons(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)

    assert window.api_key_save_btn.text() == "Validate"
    assert window.api_key_commit_btn.text() == "Save"

def test_appearance_mode_change_persists(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)

    mock_config.save.reset_mock()
    window.appearance_combo.setCurrentText("Dark")

    mock_config.set.assert_any_call("appearance_mode", "dark")
    mock_config.save.assert_called()

def test_device_change(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    # Populate dummy devices
    window.set_device_list([(0, "Mic 1"), (1, "Mic 2")])
    
    with qtbot.waitSignal(window.config_changed) as blocker:
        window.device_combo.setCurrentIndex(1)
        
    assert blocker.args[0] == "input_device_index"
    assert blocker.args[1] == 1

def test_toggle_formatter(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    # Initially False
    assert window.model_combo.isEnabled() is False
    
    # Toggle On
    window.format_toggle.setChecked(True)
    assert window.model_combo.isEnabled() is True
    
    # Click SAVE no longer needed - auto-save on toggle change
    mock_config.set.assert_any_call("use_formatter", True)
    mock_config.save.assert_called()  # Auto-save fires

def test_animated_toggle_paint(qtbot):
    toggle = AnimatedToggle()
    qtbot.addWidget(toggle)
    toggle.show()
    
    # Force paint event
    toggle.repaint()
    
    toggle.setChecked(True)
    toggle.repaint()

    toggle.setChecked(False) # Animate back
    toggle.repaint()
    
    # Test property
    toggle.handle_position = 10.0
    assert toggle.handle_position == 10.0


def test_set_model_list(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    window.set_model_list(["m1", "m2"])
    assert window.model_combo.count() == 2
    
    # Enable formatter so model combobox fires change events
    window.format_toggle.setChecked(True)
    mock_config.save.reset_mock()
    
    # Test on_model_changed logic
    window.model_combo.setCurrentText("m2")
    
    # Auto-save fires on model change
    mock_config.set.assert_any_call("formatter_model", "m2")
    mock_config.save.assert_called()

def test_visualizer_integration(app, qtbot, mock_config):
    """Visualizer updates should be safe even without embedded tester UI."""
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    window.show()

    assert not hasattr(window, "mic_test_viz")
    window.update_visualizer_level(0.75)

def test_api_key_submit_emits_config_changed(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    window.show()

    window.api_key_input.setText("gsk_valid_key")
    with qtbot.waitSignal(window.config_changed) as blocker:
        window.on_api_key_save_clicked()

    assert blocker.args[0] == "api_key"
    assert blocker.args[1] == "gsk_valid_key"
    assert window.api_key_save_btn.isEnabled() is False
    assert window.api_key_save_btn.text() == "Validating..."

def test_api_key_empty_shows_error(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    window.show()

    window.api_key_input.setText("   ")
    window.on_api_key_save_clicked()

    assert window.api_key_hint.text() == "Enter a valid Groq API key."
    assert window.api_key_save_btn.isEnabled() is True
