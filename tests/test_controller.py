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
    
    # Initial state: not recording
    mock_deps["recorder"].is_recording = False
    
    controller.toggle_recording()
    
    # Should start recording
    mock_deps["recorder"].start_recording.assert_called_once()
    mock_deps["visualizer"].show.assert_called_once()
    mock_deps["window"].set_recording_state.assert_called_with(True)

    # Toggle off
    mock_deps["recorder"].is_recording = True # Simulate state change
    controller.toggle_recording()
    
    mock_deps["recorder"].stop_recording.assert_called_once()
    mock_deps["visualizer"].hide.assert_called_once()
    mock_deps["window"].set_recording_state.assert_called_with(False)

def test_on_config_changed(app, mock_deps):
    controller = WhisperAppController()
    
    controller.on_config_changed("api_key", "new_key")
    mock_deps["groq"].update_api_key.assert_called_with("new_key")
    
    controller.on_config_changed("input_device_index", 2)
    mock_deps["recorder"].update_device.assert_called_with(2)

def test_start_transcription(app, mock_deps, qtbot):
    controller = WhisperAppController()
    
    with patch("src.controller.TranscriptionWorker") as mock_worker_cls:
        mock_worker = mock_worker_cls.return_value
        
        controller.start_transcription("test.wav")
        
        mock_worker_cls.assert_called()
        mock_worker.start.assert_called_once()

def test_transcription_worker_run(qtbot):
    mock_groq = MagicMock()
    mock_groq.transcribe.return_value = "Raw Text"
    
    worker = TranscriptionWorker(mock_groq, "file.wav", False, "model")
    
    with qtbot.waitSignal(worker.finished) as blocker:
        worker.run()
    
    assert blocker.args[0] == "Raw Text"
    assert blocker.args[1] == "Raw Text"

def test_transcription_worker_format(qtbot):
    mock_groq = MagicMock()
    mock_groq.transcribe.return_value = "Raw Text"
    mock_groq.format_text.return_value = "Formatted Text"
    
    worker = TranscriptionWorker(mock_groq, "file.wav", True, "model")
    
    with qtbot.waitSignal(worker.finished) as blocker:
        worker.run()
    
    assert blocker.args[0] == "Raw Text"
    assert blocker.args[1] == "Formatted Text"

def test_transcription_worker_error(qtbot):
    mock_groq = MagicMock()
    mock_groq.transcribe.side_effect = Exception("Fail")
    
    worker = TranscriptionWorker(mock_groq, "file.wav", False, "model")
    
    with qtbot.waitSignal(worker.error) as blocker:
        worker.run()
    
    assert "Fail" in blocker.args[0]

def test_first_run_check(app, mock_deps):
    # Mock config to return empty api key
    mock_deps["config"].get.side_effect = lambda key, default=None: {
        "api_key": "", # Empty
    }.get(key, default)
    
    # Mock QInputDialog/QMessageBox
    with patch("PyQt6.QtWidgets.QInputDialog.getText", return_value=("key", True)), \
         patch("PyQt6.QtWidgets.QMessageBox.exec"):
        
        controller = WhisperAppController()
        mock_deps["config"].set.assert_called_with("api_key", "key")

def test_quit_application(app, mock_deps):
    controller = WhisperAppController()
    mock_deps["recorder"].is_recording = True
    
    with patch.object(controller.app, "quit") as mock_quit:
        controller.quit_application()
        
        mock_deps["recorder"].stop_recording.assert_called()
        mock_deps["hotkey"].stop_listening.assert_called()
        mock_deps["window"].close.assert_called()
        mock_quit.assert_called()

def test_on_transcription_complete(app, mock_deps):
    controller = WhisperAppController()
    
    with patch("src.controller.pyperclip.copy") as mock_copy, \
         patch("src.controller.keyboard.send") as mock_send, \
         patch("src.controller.time.sleep"):
        
        controller.on_transcription_complete("raw", "final")
        
        mock_deps["window"].update_log.assert_called()
        mock_copy.assert_called_with("final")
        mock_send.assert_called_with("ctrl+v")