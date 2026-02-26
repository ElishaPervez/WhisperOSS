import pytest
from unittest.mock import MagicMock, patch, call
from PyQt6.QtWidgets import QApplication
from src.controller import WhisperAppController

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
            "hotkey_class": mock_hotkey_package,
            "window": mock_win_package.return_value,
            "visualizer": mock_vis_package.return_value,
            "tray": mock_tray_package.return_value
        }

def test_controller_init(app, mock_deps):
    controller = WhisperAppController()
    
    mock_deps["config"].get.assert_called()
    mock_deps["groq"].check_connection.assert_called() # refresh_models called
    mock_deps["recorder"].list_devices.assert_called()
    # Controller launches with the main window visible.
    mock_deps["window"].show.assert_called_once()

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
    mock_deps["visualizer"].set_processing_mode.assert_called_once()
    mock_deps["window"].set_recording_state.assert_called_with(False)

def test_hotkey_bindings_for_search_and_image(app, mock_deps):
    controller = WhisperAppController()
    del controller  # silence lints; construction is what we validate

    calls = mock_deps["hotkey_class"].call_args_list
    assert len(calls) >= 3

    # 1) Ctrl+Win transcribe, 2) Win+Ctrl search, 3) Win+Alt image search
    search_kwargs = calls[1].kwargs
    image_kwargs = calls[2].kwargs
    assert search_kwargs["modifiers"] == ["win"]
    assert search_kwargs["trigger_key"] == "ctrl"
    assert image_kwargs["modifiers"] == ["win"]
    assert image_kwargs["trigger_key"] == "alt"

def test_search_progress_signal_updates_processing_step(app, mock_deps):
    controller = WhisperAppController()

    controller._on_search_progress("Searching web")

    mock_deps["visualizer"].set_processing_step.assert_called_with(
        "Searching web",
        reason="SearchWorker.progress signal",
    )

def test_search_stream_signal_shows_and_updates_streaming_answer(app, mock_deps):
    controller = WhisperAppController()

    controller._on_search_stream_text("Hello")
    controller._on_search_stream_text("Hello world")

    mock_deps["visualizer"].begin_streaming_answer.assert_called_once_with(
        reason="first streamed answer chunk"
    )
    assert mock_deps["visualizer"].update_streaming_answer.call_count == 2

def test_on_transcription_complete(app, mock_deps):
    controller = WhisperAppController()

    with patch.object(controller, "_snapshot_clipboard_payload", return_value={"text/plain": b"old"}), \
         patch.object(controller, "_set_clipboard_text", return_value=True), \
         patch.object(controller, "_schedule_clipboard_restore"), \
         patch("src.controller.keyboard.send") as mock_send, \
         patch("src.controller.time.sleep"):
        controller.on_transcription_complete("raw", "final")

        mock_deps["window"].update_log.assert_called()
        mock_send.assert_called_once_with("ctrl+v")
        mock_deps["visualizer"].play_completion_and_hide.assert_called_once_with(
            reason="paste completed"
        )


def test_on_search_complete_shows_answer_in_visualizer(app, mock_deps):
    controller = WhisperAppController()

    with patch.object(controller, "paste_text") as mock_paste:
        controller.on_search_complete("  Paris  ")

    mock_deps["window"].update_log.assert_any_call("Answer: Paris")
    mock_deps["visualizer"].show_answer.assert_called_once_with(
        "Paris",
        reason="search pipeline completed",
    )
    mock_paste.assert_not_called()

def test_on_search_complete_finalizes_streaming_card_when_stream_was_active(app, mock_deps):
    controller = WhisperAppController()
    controller._search_stream_started = True

    controller.on_search_complete("  Stream final  ")

    mock_deps["visualizer"].complete_streaming_answer.assert_called_once_with(
        "Stream final",
        reason="search pipeline completed after streaming",
    )

def test_paste_text_failure_schedules_quick_restore_and_signals_failure(app, mock_deps):
    controller = WhisperAppController()
    mock_deps["visualizer"].cancel_processing.reset_mock()

    with patch.object(controller, "_snapshot_clipboard_payload", return_value={"text/plain": b"old"}), \
         patch.object(controller, "_set_clipboard_text", return_value=False), \
         patch.object(controller, "_schedule_clipboard_restore") as mock_schedule_restore, \
         patch.object(controller.app.clipboard(), "text", return_value="old"), \
         patch("src.controller.keyboard.send") as mock_send:
        controller.paste_text("final")

    mock_send.assert_not_called()
    mock_schedule_restore.assert_called_once_with(
        {"text/plain": b"old"},
        fallback_text="old",
        initial_delay_ms=60,
    )
    mock_deps["visualizer"].cancel_processing.assert_called_once_with(reason="paste failed")

def test_paste_text_uses_clipboard_paste_and_restore(app, mock_deps):
    controller = WhisperAppController()
    mock_deps["visualizer"].cancel_processing.reset_mock()

    with patch.object(controller, "_snapshot_clipboard_payload", return_value={"text/plain": b"old"}), \
         patch.object(controller, "_set_clipboard_text", return_value=True), \
         patch.object(controller, "_schedule_clipboard_restore") as mock_schedule_restore, \
         patch.object(controller.app.clipboard(), "text", return_value="old"), \
         patch("src.controller.keyboard.send") as mock_send, \
         patch("src.controller.time.sleep"):
        controller.paste_text("final")

    mock_send.assert_called_once_with("ctrl+v")
    mock_schedule_restore.assert_called_once_with(
        {"text/plain": b"old"},
        fallback_text="old",
        initial_delay_ms=550,
    )
    mock_deps["visualizer"].cancel_processing.assert_not_called()

def test_start_transcription_search_passes_selected_text(app, mock_deps):
    controller = WhisperAppController()
    controller.recording_mode = "search"

    with patch.object(controller, "_capture_selected_text", return_value="quixotic"), \
         patch("src.controller.SearchWorker") as mock_worker_cls:
        mock_worker_inst = mock_worker_cls.return_value
        controller.start_transcription("dummy.wav")

    _, kwargs = mock_worker_cls.call_args
    assert kwargs["selected_text"] == "quixotic"
    mock_worker_inst.start.assert_called_once()

def test_start_transcription_search_image_transcribes_before_capture(app, mock_deps):
    controller = WhisperAppController()
    controller.recording_mode = "search_image"
    mock_deps["config"].get.side_effect = lambda key, default=None: {
        "api_key": "test_key",
        "input_device_index": 0,
        "use_formatter": False,
        "formatter_model": "test_model",
        "use_antigravity_proxy_search": True,
    }.get(key, default)

    with patch("src.controller.TranscriptionWorker") as mock_transcription_worker_cls:
        mock_worker_inst = mock_transcription_worker_cls.return_value
        controller.start_transcription("dummy.wav")

    _, kwargs = mock_transcription_worker_cls.call_args
    assert kwargs["use_formatter"] is False
    assert kwargs["format_model"] == "test_model"
    mock_worker_inst.start.assert_called_once()

def test_start_transcription_search_image_requires_proxy_when_disabled(app, mock_deps):
    controller = WhisperAppController()
    controller.recording_mode = "search_image"
    mock_deps["config"].get.side_effect = lambda key, default=None: {
        "api_key": "test_key",
        "input_device_index": 0,
        "use_formatter": False,
        "formatter_model": "test_model",
        "use_antigravity_proxy_search": False,
    }.get(key, default)

    with patch.object(controller, "_show_proxy_required_notice") as mock_notice, \
         patch("src.controller.TranscriptionWorker") as mock_transcription_worker_cls:
        controller.start_transcription("dummy.wav")

    mock_notice.assert_called_once()
    mock_transcription_worker_cls.assert_not_called()

def test_continue_image_search_pipeline_passes_query_and_image(app, mock_deps):
    controller = WhisperAppController()
    fake_png = b"\x89PNG\r\n\x1a\nfake"

    with patch.object(controller, "_capture_screen_region_png", return_value=fake_png), \
         patch("src.controller.SearchWorker") as mock_worker_cls:
        mock_worker_inst = mock_worker_cls.return_value
        controller._continue_image_search_pipeline("what is this", "test_model", use_proxy_search=False)

    _, kwargs = mock_worker_cls.call_args
    assert kwargs["query_text"] == "what is this"
    assert kwargs["image_png_bytes"] == fake_png
    assert kwargs["search_client"] is controller.search_client
    mock_worker_inst.start.assert_called_once()

def test_on_config_changed_api_key_valid(app, mock_deps):
    controller = WhisperAppController()
    mock_deps["config"].set.reset_mock()
    mock_deps["config"].save.reset_mock()
    mock_deps["groq"].update_api_key.reset_mock()

    with patch.object(controller, "_validate_groq_api_key", return_value=(True, "", "", "info")):
        controller.on_config_changed("api_key", "gsk_new_valid")

    mock_deps["config"].set.assert_any_call("api_key", "gsk_new_valid")
    mock_deps["config"].save.assert_called()
    mock_deps["groq"].update_api_key.assert_called_once_with("gsk_new_valid")
    mock_deps["window"].set_api_key_validation_result.assert_called_with(True, "API key validated and saved.")

def test_on_config_changed_api_key_invalid(app, mock_deps):
    controller = WhisperAppController()
    mock_deps["config"].set.reset_mock()
    mock_deps["config"].save.reset_mock()
    mock_deps["groq"].update_api_key.reset_mock()

    with patch.object(
        controller,
        "_validate_groq_api_key",
        return_value=(False, "Groq rejected this key", "The provided API key is invalid.", "error"),
    ):
        controller.on_config_changed("api_key", "bad_key")

    mock_deps["config"].set.assert_not_called()
    mock_deps["config"].save.assert_not_called()
    mock_deps["groq"].update_api_key.assert_not_called()
    mock_deps["window"].set_api_key_validation_result.assert_called_with(False, "The provided API key is invalid.")

def test_on_config_changed_animation_fps_updates_visualizer(app, mock_deps):
    controller = WhisperAppController()
    controller.on_config_changed("animation_fps", 120)
    mock_deps["visualizer"].set_animation_fps.assert_called_once_with(120)

def test_window_always_shown_on_startup(app, mock_deps):
    """Main window must be shown unconditionally during init_state."""
    WhisperAppController()
    mock_deps["window"].show.assert_called_once()


# ---------------------------------------------------------------------------
# New tests from review
# ---------------------------------------------------------------------------

def test_paste_text_empty_does_not_emit_completion(app, mock_deps):
    """Empty/whitespace text must NOT emit the paste-completed signal."""
    controller = WhisperAppController()
    mock_deps["visualizer"].play_completion_and_hide.reset_mock()
    mock_deps["visualizer"].cancel_processing.reset_mock()

    with patch.object(controller, "_set_clipboard_text") as mock_set_clipboard, \
         patch("src.controller.keyboard.send") as mock_send:
        controller.paste_text("")
        controller.paste_text("   ")
        mock_set_clipboard.assert_not_called()
        mock_send.assert_not_called()

    mock_deps["visualizer"].play_completion_and_hide.assert_not_called()
    mock_deps["visualizer"].cancel_processing.assert_called()


def test_paste_text_emits_completion_only_after_successful_ctrl_v(app, mock_deps):
    """Completion signal must be emitted after Ctrl+V dispatch, not before."""
    controller = WhisperAppController()
    call_order: list[str] = []

    def record_send(*_args, **_kwargs):
        call_order.append("send")

    controller._paste_completed_signal.connect(lambda: call_order.append("completed"))

    with patch.object(controller, "_snapshot_clipboard_payload", return_value={"text/plain": b"old"}), \
         patch.object(controller, "_set_clipboard_text", return_value=True), \
         patch.object(controller, "_schedule_clipboard_restore"), \
         patch("src.controller.keyboard.send", side_effect=record_send), \
         patch("src.controller.time.sleep"):
        controller.paste_text("hello")

    assert call_order == ["send", "completed"], (
        "completion signal must be emitted AFTER Ctrl+V dispatch, got: " + str(call_order)
    )


def test_set_clipboard_text_on_windows_does_not_fallback_to_qt_or_pyperclip(app, mock_deps):
    controller = WhisperAppController()

    with patch("src.controller.sys.platform", "win32"), \
         patch.object(controller, "_set_clipboard_text_win32", return_value=False) as mock_win32, \
         patch.object(controller.app.clipboard(), "setText") as mock_qt_set_text, \
         patch("src.controller.pyperclip.copy") as mock_pyperclip_copy:
        ok = controller._set_clipboard_text("staged text")

    assert ok is False
    mock_win32.assert_called_once_with("staged text", exclude_history=True)
    mock_qt_set_text.assert_not_called()
    mock_pyperclip_copy.assert_not_called()


def test_quit_application_stops_active_worker(app, mock_deps):
    """quit_application must call quit() and wait() on an active worker thread."""
    controller = WhisperAppController()
    mock_worker = MagicMock()
    mock_worker.wait.return_value = True
    controller.worker = mock_worker

    controller.quit_application()

    mock_worker.quit.assert_called_once()
    mock_worker.wait.assert_called_once()
    assert controller.worker is None


def test_quit_application_terminates_worker_if_wait_times_out(app, mock_deps):
    """If worker.wait() returns False (timeout), terminate() must be called."""
    controller = WhisperAppController()
    mock_worker = MagicMock()
    mock_worker.wait.side_effect = [False, None]  # first wait times out, second succeeds
    controller.worker = mock_worker

    controller.quit_application()

    mock_worker.terminate.assert_called_once()


def test_record_toggled_signal_not_connected_to_set_recording(app, mock_deps):
    """record_toggled UI signal must NOT be connected to set_recording (hotkeys only)."""
    controller = WhisperAppController()
    # The window mock's record_toggled should never have been connected.
    mock_win = mock_deps["window"]
    # record_toggled.connect should not have been called with set_recording.
    if hasattr(mock_win.record_toggled, "connect"):
        for c in mock_win.record_toggled.connect.call_args_list:
            assert c.args[0] is not controller.set_recording, (
                "record_toggled must not be connected to set_recording; use hotkeys."
            )
