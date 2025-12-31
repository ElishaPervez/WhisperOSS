import pytest
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPaintEvent, QRegion
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
    
    assert window.windowTitle() == "WhisperOSS"
    assert window.record_btn.text() == "REC"
    assert window.format_toggle.isChecked() is False

def test_record_toggle(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    with qtbot.waitSignal(window.record_toggled) as blocker:
        qtbot.mouseClick(window.record_btn, Qt.MouseButton.LeftButton)
    
    assert blocker.args[0] is True
    assert window.is_recording is True
    assert window.record_btn.text() == "STOP"

def test_device_change(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    # Populate dummy devices
    window.set_device_list([(0, "Mic 1"), (1, "Mic 2")])
    
    with qtbot.waitSignal(window.config_changed) as blocker:
        window.device_combo.setCurrentIndex(1)
        
    assert blocker.args[0] == "input_device_index"
    assert blocker.args[1] == 1
    # Note: We now save on SAVE click, but the signal still emits for immediate internal updates if needed
    # However, in our current implementation, we only call config.set in on_save_clicked.
    # So we don't expect config.set call here.

def test_device_change_invalid(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    # Trigger change with -1 (empty)
    window.on_device_changed(-1)
    # Should not call config set
    mock_config.set.assert_not_called()

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

def test_copy_log(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    window.update_log("Test Transcript")
    
    clipboard = QApplication.clipboard()
    clipboard.clear()
    
    qtbot.mouseClick(window.copy_btn, Qt.MouseButton.LeftButton)
    
    assert clipboard.text() == "Test Transcript"
    assert window.copy_btn.text() == "Copied!"
    
    # Wait for timer to reset button
    qtbot.wait(1600) 
    assert window.copy_btn.text() == "Copy"
    assert window.copy_btn.isEnabled() is True

def test_copy_log_empty(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    window.update_log("") # Empty
    
    clipboard = QApplication.clipboard()
    clipboard.clear()
    qtbot.mouseClick(window.copy_btn, Qt.MouseButton.LeftButton)
    assert clipboard.text() == ""

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

def test_pulsing_record_button_paint(qtbot):
    btn = PulsingRecordButton()
    qtbot.addWidget(btn)
    btn.show()
    btn.repaint()
    
    btn.setRecording(True)
    btn._update_pulse()
    btn.repaint()
    
    btn.setRecording(False)
    btn._update_pulse()
    btn.repaint()

def test_glass_panel_paint(qtbot):
    panel = GlassPanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.repaint()

def test_prompt_api_key(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    qtbot.addWidget(window)
    
    with patch("PyQt6.QtWidgets.QInputDialog.getText", return_value=("new_key", True)):
        window.prompt_api_key()
        
    mock_config.set.assert_called_with("api_key", "new_key")

def test_status_methods(app, qtbot, mock_config):
    window = MainWindow(mock_config)
    window._set_connected_status("Connected")
    assert "✓ Connected" in window.api_status_label.text()
    
    window._set_error_status("Error")
    assert "⚠ Error" in window.api_status_label.text()

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