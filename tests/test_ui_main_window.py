import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from unittest.mock import MagicMock, patch
from src.ui_main_window import MainWindow, AnimatedToggle, PulsingRecordButton, GlassPanel

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
    
    # Click SAVE to trigger config update
    qtbot.mouseClick(window.save_btn, Qt.MouseButton.LeftButton)
    mock_config.set.assert_any_call("use_formatter", True)

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

def test_prompt_api_key(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    with patch("PyQt6.QtWidgets.QInputDialog.getText", return_value=("new_key", True)):
        window.prompt_api_key()
        
    # The prompt_api_key method in MainWindow triggers config set directly
    mock_config.set.assert_called_with("api_key", "new_key")

def test_set_model_list(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    window.set_model_list(["m1", "m2"])
    assert window.model_combo.count() == 2
    
    # Test on_model_changed logic
    window.model_combo.setCurrentText("m2")
    
    # Click SAVE
    qtbot.mouseClick(window.save_btn, Qt.MouseButton.LeftButton)
    mock_config.set.assert_any_call("formatter_model", "m2")
