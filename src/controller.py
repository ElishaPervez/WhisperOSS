import sys
import threading
import time
import ctypes
import keyboard
import pyperclip
import logging
import io
from typing import Optional, Any
from groq import Groq as GroqRaw, AuthenticationError as GroqAuthError, APIConnectionError as GroqConnError
from PyQt6.QtWidgets import QApplication, QDialog, QSystemTrayIcon, QMenu
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QCursor


from src.config_manager import ConfigManager
from src.audio_recorder import AudioRecorder
from src.groq_client import GroqClient
from src.hotkey_manager import HotkeyManager
from src.ui_main_window import MainWindow
from src.ui_onboarding import SetupMessageDialog, ApiKeyInputDialog
from src.ui_visualizer import AudioVisualizer
from src.services.groq_service import TranscriptionWorker, SearchWorker

# Configure logger
logger = logging.getLogger(__name__)


def get_active_window_title() -> str:
    """Get the title of the currently active window using Win32 API."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value
    except Exception as e:
        logger.debug(f"Could not get active window title: {e}")
    return ""

class WhisperAppController(QObject):
    # Thread-safe signals for hotkey events
    _start_recording_signal = pyqtSignal()
    _stop_recording_signal = pyqtSignal()

    # New signals for search mode
    _start_search_signal = pyqtSignal()
    _stop_search_signal = pyqtSignal()
    _paste_completed_signal = pyqtSignal()
    _paste_failed_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False) # Keep running for system tray

        self.recording_mode = "transcribe" # "transcribe" or "search"
        self._show_window_after_setup = False

        # Load config first
        self.config = ConfigManager()

        # Connect hotkey signals to recording actions (thread-safe)
        self._start_recording_signal.connect(lambda: self.set_recording(True, "transcribe"))
        self._stop_recording_signal.connect(lambda: self.set_recording(False))

        self._start_search_signal.connect(lambda: self.set_recording(True, "search"))
        self._stop_search_signal.connect(lambda: self.set_recording(False))
        self._paste_completed_signal.connect(self._on_paste_completed)
        self._paste_failed_signal.connect(self._on_paste_failed)

        # Check for first run (no API key) and prompt before initializing
        self._check_first_run_api_key()
        self.groq = GroqClient(self.config.get("api_key"))
        self.recorder = AudioRecorder(self.config.get("input_device_index"))

        # Standard Hotkey: Ctrl+Win (Transcribe)
        self.hotkey_mgr = HotkeyManager(
            modifiers=['ctrl'],
            trigger_key='win',
            on_start=self._start_recording_signal.emit,
            on_stop=self._stop_recording_signal.emit
        )

        # Search Hotkey: Win+Ctrl (Quick Answer)
        self.search_hotkey = HotkeyManager(
            modifiers=['win'], # Logic handles left/right windows
            trigger_key='ctrl',
            on_start=self._start_search_signal.emit,
            on_stop=self._stop_search_signal.emit
        )

        # UI
        self.window = MainWindow(self.config)
        self.visualizer = AudioVisualizer(animation_fps=self.config.get("animation_fps", 100))

        # System Tray
        self.setup_system_tray()

        # Override window close to minimize to tray
        self.window.closeEvent = self.on_window_close

        # Connections
        self.connect_signals()
        self.init_state()

        self.worker: Optional[QObject] = None

    def _check_first_run_api_key(self) -> None:
        """Prompt for API key on first run, validating against the Groq API."""
        api_key = self.config.get("api_key", "")

        if not api_key or api_key.strip() == "":
            welcome = SetupMessageDialog(
                title="Welcome to WhisperOSS",
                heading="Welcome to WhisperOSS",
                body=(
                    "Before you start dictating, connect a Groq API key. "
                    "You can create one in the Groq Console in under a minute."
                ),
                severity="info",
                primary_text="Continue",
                secondary_text="Exit",
            )
            if welcome.exec() != int(QDialog.DialogCode.Accepted):
                sys.exit(0)

            # Keep prompting until valid key or user exits.
            previous_input = ""
            while True:
                key_dialog = ApiKeyInputDialog(initial_key=previous_input)
                if key_dialog.exec() != int(QDialog.DialogCode.Accepted):
                    confirm_exit = SetupMessageDialog(
                        title="API Key Required",
                        heading="WhisperOSS needs an API key",
                        body=(
                            "Transcription cannot run without a Groq API key. "
                            "Exit now or go back to paste your key."
                        ),
                        severity="warning",
                        primary_text="Exit App",
                        secondary_text="Back",
                    )
                    if confirm_exit.exec() == int(QDialog.DialogCode.Accepted):
                        sys.exit(0)
                    continue

                entered_key = key_dialog.api_key()
                previous_input = entered_key

                is_valid, error_heading, error_message, severity = self._validate_groq_api_key(entered_key)
                if not is_valid:
                    SetupMessageDialog(
                        title="API Key Validation Failed",
                        heading=error_heading,
                        body=error_message,
                        severity=severity,
                    ).exec()
                    continue

                self.config.set("api_key", entered_key)
                self.config.save()
                self._show_window_after_setup = True
                logger.info("API key validated and saved successfully.")
                break

    def _validate_groq_api_key(self, api_key: str) -> tuple[bool, str, str, str]:
        """Validate API key by calling an authenticated Groq endpoint."""
        normalized_key = (api_key or "").strip()
        if not normalized_key:
            return False, "Missing API key", "Enter a valid Groq API key.", "error"

        try:
            test_client = GroqRaw(api_key=normalized_key)
            test_client.models.list()
            return True, "", "", "info"
        except GroqAuthError:
            return (
                False,
                "Groq rejected this key",
                "The provided API key is invalid. Paste a valid key from console.groq.com.",
                "error",
            )
        except GroqConnError:
            return (
                False,
                "Could not reach Groq",
                "Network connection failed while validating the key. Check connectivity and retry.",
                "warning",
            )
        except Exception as exc:
            return (
                False,
                "Could not validate the key",
                f"{exc}",
                "warning",
            )

    def connect_signals(self) -> None:
        # UI -> Logic
        self.window.record_toggled.connect(self.set_recording)
        self.window.config_changed.connect(self.on_config_changed)

        # Recorder -> Floating visualizer overlay
        self.recorder.visualizer_update.connect(self.visualizer.update_level)
        self.recorder.visualizer_update.connect(self.window.update_visualizer_level)
        self.recorder.recording_finished.connect(self.start_transcription)
        self.recorder.error_occurred.connect(self.show_error)

    def init_state(self) -> None:
        # Populate Devices
        devices = self.recorder.list_devices()
        self.window.set_device_list(devices)

        # Populate Models (Async preferred but sync for init is ok)
        self.refresh_models()

        # Start global listeners
        self.hotkey_mgr.start_listening()
        self.search_hotkey.start_listening()

        # Always open visible on startup instead of tray-only.
        self.show_window()

    def on_config_changed(self, key: str, value: Any) -> None:
        if key == "api_key":
            new_key = str(value).strip()
            is_valid, heading, message, _ = self._validate_groq_api_key(new_key)
            if not is_valid:
                self.window.set_api_key_validation_result(False, message)
                self.window._set_error_status("API Key Invalid / Missing")
                logger.warning(f"Rejected API key update: {heading}")
                return

            self.config.set("api_key", new_key)
            self.config.save()
            self.groq.update_api_key(new_key)
            self.refresh_models()
            self.window.set_api_key_validation_result(True, "API key validated and saved.")
        elif key == "input_device_index":
            self.recorder.update_device(value)
        elif key == "animation_fps":
            self.visualizer.set_animation_fps(value)

    def refresh_models(self) -> None:
        # In a real app, do this async
        if self.groq.check_connection():
            _, llm_models = self.groq.list_models()
            if llm_models:
                self.window.set_model_list(llm_models)
                self.window._set_connected_status("API Connected")
            else:
                self.window._set_connected_status("API Connected (No Models)")
        else:
            self.window._set_error_status("API Key Invalid / Missing")

    def toggle_recording(self) -> None:
        # Toggle state - Defaults to standard transcription mode if toggled via UI
        is_rec = not self.recorder.is_recording
        self.set_recording(is_rec, "transcribe")

    def set_recording(self, recording: bool, mode: str="transcribe") -> None:
        # Update UI state (thread-safe signal)
        self.window.set_recording_state(recording)

        if recording:
            self.recording_mode = mode
            self.visualizer.set_listening_mode()
            # Show first, then position - some window systems reset position during show()
            self.visualizer.show()
            self._position_visualizer_at_cursor()
            self.recorder.start_recording()
        else:
            # Keep visualizer visible and switch to a processing animation
            # while the API request and transcription are in progress.
            self.visualizer.set_processing_mode()
            self.recorder.stop_recording()



    def _position_visualizer_at_cursor(self) -> None:
        """Position the visualizer at center-bottom of the screen where the cursor is located."""
        cursor_pos = QCursor.pos()

        # Find which screen contains the cursor
        screen = self.app.screenAt(cursor_pos)
        if screen is None:
            screen = self.app.primaryScreen()

        screen_geo = screen.geometry()
        vis_width = self.visualizer.width()
        vis_height = self.visualizer.height()

        # Center horizontally on that screen, position near bottom
        x = screen_geo.x() + (screen_geo.width() - vis_width) // 2
        y = screen_geo.y() + screen_geo.height() - vis_height - 60  # 60px from bottom for taskbar

        # Clamp to ensure visualizer stays within this screen's bounds
        x = max(screen_geo.x(), min(x, screen_geo.x() + screen_geo.width() - vis_width))
        y = max(screen_geo.y(), min(y, screen_geo.y() + screen_geo.height() - vis_height))

        logger.info(f"Cursor at: {cursor_pos.x()}, {cursor_pos.y()}")
        logger.info(f"Screen: {screen.name()} - Geometry: {screen_geo}")
        logger.info(f"Positioning visualizer at: ({x}, {y})")

        # Move and then explicitly set the position to ensure it sticks
        self.visualizer.move(x, y)

    def start_transcription(self, audio_source: Any) -> None:
        """Start transcription. audio_source can be BytesIO buffer or file path."""
        self.window.update_log(f"Processing ({self.recording_mode})...")

        # Get common config
        use_fmt = self.config.get("use_formatter")
        fmt_model = self.config.get("formatter_model", "openai/gpt-oss-120b") # Default if missing

        if self.recording_mode == "search":
            # Quick Answer Mode
            logger.info(f"Starting Quick Answer search (Refiner: {fmt_model})...")
            # Reuse the formatter model (High Intelligence) for refinement
            self.worker = SearchWorker(self.groq, audio_source, refinement_model_id=fmt_model)
            self.worker.finished.connect(self.on_search_complete)
            self.worker.error.connect(self.show_error)
            self.worker.start()

        else:
            # Standard Transcription Mode
            use_trans = self.config.get("translation_enabled")
            target_lang = self.config.get("target_language")
            fmt_style = self.config.get("formatting_style", "Default")

            # Get active window context for context intelligence
            active_context = get_active_window_title()

            logger.info(f"Starting transcription: fmt={use_fmt}, trans={use_trans}, lang={target_lang}, style={fmt_style}, context={active_context}")

            self.worker = TranscriptionWorker(
                self.groq, audio_source, use_fmt, fmt_model,
                use_translation=use_trans, target_language=target_lang,
                formatting_style=fmt_style, active_context=active_context
            )
            self.worker.finished.connect(self.on_transcription_complete)
            self.worker.error.connect(self.show_error)
            self.worker.start()

    def on_transcription_complete(self, raw: str, final: str) -> None:
        self.window.update_log("Transcription complete")
        self.paste_text(final)

    def on_search_complete(self, answer: str) -> None:
        self.window.update_log(f"Answer: {answer}")
        self.paste_text(answer)



    def paste_text(self, text: str) -> None:
        """Ghost paste: backup clipboard, paste text, restore original clipboard."""
        # Transition out of processing immediately when transcription is ready.
        # Clipboard operations can occasionally block, and should not delay UI state.
        self._paste_completed_signal.emit()

        def _smart_paste():
            original_clipboard = None
            try:
                # 1. Backup current clipboard
                try:
                    original_clipboard = pyperclip.paste()
                except Exception:
                    original_clipboard = None

                # 2. Copy transcription and paste
                pyperclip.copy(text.strip())
                time.sleep(0.05)  # Brief settle time
                keyboard.send('ctrl+v')

            except Exception as e:
                logger.error(f"Smart paste failed: {e}")
                self._paste_failed_signal.emit()
                return

            # 3. Restore original clipboard after delay (best-effort, non-blocking for UI transitions)
            if original_clipboard is not None:
                try:
                    time.sleep(0.5)  # Wait for paste to complete
                    pyperclip.copy(original_clipboard)
                    logger.debug("Clipboard restored to original content")
                except Exception as e:
                    logger.debug(f"Clipboard restore skipped: {e}")

        # Run in background thread to avoid blocking
        threading.Thread(target=_smart_paste, daemon=True).start()

    def _on_paste_completed(self) -> None:
        self.visualizer.play_completion_and_hide()

    def _on_paste_failed(self) -> None:
        self.visualizer.cancel_processing()

    def show_error(self, msg: str) -> None:
        self.window.update_log(f"Error: {msg}")
        self.visualizer.cancel_processing()
        # Also show a tray notification so the user sees it even if window is hidden
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "WhisperOSS Error",
                str(msg),
                QSystemTrayIcon.MessageIcon.Critical,
                4000
            )

    def setup_system_tray(self) -> None:
        """Setup system tray icon and menu"""
        self.tray_icon = QSystemTrayIcon(self.app)

        # Use a default icon or create one
        icon = self.app.style().standardIcon(self.app.style().StandardPixmap.SP_MediaPlay)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("WhisperOSS - Voice to Text")

        # Create tray menu
        tray_menu = QMenu()

        show_action = QAction("Show WhisperOSS", self.app)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self.app)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # Left-click to show window
        self.tray_icon.activated.connect(self.on_tray_activated)

        self.tray_icon.show()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (left or right click)"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left click
            self.show_window()
        elif reason == QSystemTrayIcon.ActivationReason.Context:  # Right click
            # Context menu is shown automatically
            pass

    def show_window(self) -> None:
        """Show and raise the main window"""
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def on_window_close(self, event: Any) -> None:
        """Hide to system tray instead of closing"""
        event.ignore()
        self.window.hide()
        self.tray_icon.showMessage(
            "WhisperOSS",
            "Application minimized to system tray. Right-click or left-click to restore.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def quit_application(self) -> None:
        """Properly quit the application, stopping all threads"""
        # Stop recording if active
        if self.recorder.is_recording:
            self.recorder.stop_recording()

        # Stop hotkey listener
        self.hotkey_mgr.stop_listening()
        self.search_hotkey.stop_listening()

        # Hide tray icon
        self.tray_icon.hide()

        # Close windows
        self.window.close()
        self.visualizer.close()

        # Quit the application
        self.app.quit()

    def run(self) -> None:
        sys.exit(self.app.exec())
