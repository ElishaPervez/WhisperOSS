import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from src.controller import WhisperAppController, TranscriptionWorker

@pytest.fixture
def app(qtbot):
    return QApplication.instance() or QApplication([])

@pytest.fixture
def mock_deps():
    with patch("src.controller.ConfigManager") as mock_cfg, \
         patch("src.controller.GroqClient") as mock_groq_package, \
         patch("src.controller.AudioRecorder") as mock_rec_package, \
         patch("src.controller.HotkeyManager") as mock_hotkey_package, \
         patch("src.controller.MainWindow") as mock_win_package, \
         patch("src.controller.AudioVisualizer") as mock_vis_package, \
         patch("src.controller.QSystemTrayIcon") as mock_tray_package:
        
        # Setup Config defaults
        mock_cfg_inst = mock_cfg.return_value
        mock_cfg_inst.get.side_effect = lambda key, default=None: {
            "api_key": "test_key",
            "input_device_index": 0,
            "use_formatter": False,
            "formatter_model": "test_model"
        }.get(key, default)
        
        # Setup Groq defaults
        mock_groq_inst = mock_groq_package.return_value
        mock_groq_inst.check_connection.return_value = True
        mock_groq_inst.list_models.return_value = (["whisper-1"], ["llama3"])
        
        # Setup Recorder defaults
        mock_rec_inst = mock_rec_package.return_value
        mock_rec_inst.list_devices.return_value = [(0, "Default")]
        
        yield {
            "config": mock_cfg_inst,
            "groq": mock_groq_inst,
            "recorder": mock_rec_inst,
            "hotkey": mock_hotkey_package.return_value,
            "window": mock_win_package.return_value,
            "visualizer": mock_vis_package.return_value,
            "tray": mock_tray_package.return_value
        }

def test_controller_init(app, mock_deps):
    controller = WhisperAppController()
    
    mock_deps["config"].get.assert_called()
    mock_deps["groq"].check_connection.assert_called() # refresh_models called
    mock_deps["recorder"].list_devices.assert_called()
    mock_deps["window"].show.assert_called()

def test_toggle_recording(app, mock_deps):
    controller = WhisperAppController()
    
    # Mock the internal positioning method to avoid QScreen/Geometry logic in test
    controller._position_visualizer_at_cursor = MagicMock()
    
    # Initial state: not recording
    mock_deps["recorder"].is_recording = False
    
    controller.toggle_recording()
    
    # Should start recording
    mock_deps["recorder"].start_recording.assert_called_once()
    mock_deps["visualizer"].show.assert_called_once()
    mock_deps["window"].set_recording_state.assert_called_with(True)
    # Check that we tried to position it
    controller._position_visualizer_at_cursor.assert_called_once()

    # Toggle off
    mock_deps["recorder"].is_recording = True # Simulate state change
    controller.toggle_recording()
    
    mock_deps["recorder"].stop_recording.assert_called_once()
    mock_deps["visualizer"].hide.assert_called_once()
    mock_deps["window"].set_recording_state.assert_called_with(False)

def test_on_transcription_complete(app, mock_deps):
    controller = WhisperAppController()
    
    with patch("src.controller.pyperclip.copy") as mock_copy, \
         patch("src.controller.pyperclip.paste") as mock_paste, \
         patch("src.controller.keyboard.send") as mock_send, \
         patch("src.controller.time.sleep"), \
         patch("src.controller.threading.Thread") as mock_thread_cls:
        
        # Configure the mock thread to run the target immediately (synchronous test)
        def run_target(target=None, daemon=False):
            target() # Execute the closure immediately
            return MagicMock() # Return a dummy thread object
        
        mock_thread_cls.side_effect = run_target
        
        controller.on_transcription_complete("raw", "final")
        
        mock_deps["window"].update_log.assert_called()
        
        # Now we can assert, because run_target executed the logic
        # Use assert_any_call because copy is called twice (text + restore)
        mock_copy.assert_any_call("final")
        mock_send.assert_called_with('ctrl+v')