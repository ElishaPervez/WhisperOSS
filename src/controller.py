import sys
import time
import ctypes
import keyboard
import pyperclip
import logging
import io
from typing import Optional, Any
from groq import Groq as GroqRaw, AuthenticationError as GroqAuthError, APIConnectionError as GroqConnError
from PyQt6.QtWidgets import QApplication, QDialog, QSystemTrayIcon, QMenu
from PyQt6.QtCore import QObject, pyqtSignal, QByteArray, QBuffer, QIODevice, Qt, QTimer, QMimeData
from PyQt6.QtGui import QIcon, QAction, QCursor


from src.config_manager import ConfigManager
from src.audio_recorder import AudioRecorder
from src.groq_client import GroqClient
from src.proxy_search_client import ProxySearchClient
from src.hotkey_manager import HotkeyManager
from src.ui_main_window import MainWindow
from src.ui_onboarding import SetupMessageDialog, ApiKeyInputDialog
from src.ui_visualizer import AudioVisualizer
from src.ui_screen_snip import ScreenRegionSelector
from src.services.groq_service import TranscriptionWorker, SearchWorker
from src.debug_trace import configure_debug_trace, trace_widget_event

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
    _start_image_search_signal = pyqtSignal()
    _stop_image_search_signal = pyqtSignal()
    _paste_completed_signal = pyqtSignal()
    _paste_failed_signal = pyqtSignal()
    _search_progress_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._debug_path = configure_debug_trace()
        trace_widget_event(
            "controller_init",
            trigger="WhisperAppController.__init__",
            reason="controller startup",
            debug_path=str(self._debug_path),
        )
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False) # Keep running for system tray

        self.recording_mode = "transcribe" # "transcribe" or "search"

        # Load config first
        self.config = ConfigManager()

        # Connect hotkey signals to recording actions (thread-safe)
        self._start_recording_signal.connect(lambda: self.set_recording(True, "transcribe"))
        self._stop_recording_signal.connect(lambda: self.set_recording(False))

        self._start_search_signal.connect(lambda: self.set_recording(True, "search"))
        self._stop_search_signal.connect(lambda: self.set_recording(False))
        self._start_image_search_signal.connect(lambda: self.set_recording(True, "search_image"))
        self._stop_image_search_signal.connect(lambda: self.set_recording(False))
        self._paste_completed_signal.connect(self._on_paste_completed)
        self._paste_failed_signal.connect(self._on_paste_failed)
        self._search_progress_signal.connect(self._on_search_progress)

        # Check for first run (no API key) and prompt before initializing
        self._check_first_run_api_key()
        self.groq = GroqClient(self.config.get("api_key"))
        self.search_client = ProxySearchClient(
            base_url=self.config.get("antigravity_proxy_url", "http://127.0.0.1:8045"),
            api_key=self.config.get("antigravity_api_key", ""),
            primary_model=self.config.get("antigravity_search_model", "gemini-3-flash"),
            fallback_model=self.config.get(
                "antigravity_search_fallback_model", "gemini-2.5-flash"
            ),
            thinking_level=self.config.get("antigravity_thinking_level", "high"),
        )
        self.recorder = AudioRecorder(self.config.get("input_device_index"))

        # Standard Hotkey: Ctrl+Win (Transcribe)
        self.hotkey_mgr = HotkeyManager(
            modifiers=['ctrl'],
            trigger_key='win',
            on_start=self._start_recording_signal.emit,
            on_stop=self._stop_recording_signal.emit,
            forbidden_keys=['shift'],
            activation_delay_ms=85,
        )

        # Search Hotkey: Win+Ctrl (Quick Answer)
        self.search_hotkey = HotkeyManager(
            modifiers=['win'], # Logic handles left/right windows
            trigger_key='ctrl',
            on_start=self._start_search_signal.emit,
            on_stop=self._stop_search_signal.emit,
            forbidden_keys=['shift'],
            activation_delay_ms=85,
        )

        # Visual Search Hotkey: Win+Alt (crosshair area + voice question)
        self.image_search_hotkey = HotkeyManager(
            modifiers=['win'],
            trigger_key='alt',
            on_start=self._start_image_search_signal.emit,
            on_stop=self._stop_image_search_signal.emit,
        )

        # UI
        self.window = MainWindow(self.config)
        self.visualizer = AudioVisualizer(animation_fps=self.config.get("animation_fps", 100))
        self.visualizer.set_stream_realtime_enabled(
            bool(self.config.get("stream_realtime_enabled", True))
        )
        self.visualizer.set_stream_reveal_wps(
            self.config.get("stream_reveal_wps", 8)
        )
        self.visualizer.set_stream_catch_up_enabled(
            bool(self.config.get("stream_catch_up_enabled", True))
        )

        # System Tray
        self.setup_system_tray()

        # Override window close to minimize to tray
        self.window.closeEvent = self.on_window_close

        # Connections
        self.connect_signals()
        self.init_state()

        self.worker: Optional[QObject] = None
        self._search_stream_started = False

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
        # record_toggled is intentionally not connected here; recording is driven
        # exclusively by HotkeyManager signals.  The signal is retained in
        # MainWindow for callers that may want to add a UI record button later.
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
        self.image_search_hotkey.start_listening()

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
        elif key == "stream_realtime_enabled":
            enabled = bool(value)
            self.config.set("stream_realtime_enabled", enabled)
            self.config.save()
            self.visualizer.set_stream_realtime_enabled(enabled)
        elif key == "stream_reveal_wps":
            try:
                wps = int(value)
            except (TypeError, ValueError):
                wps = 8
            wps = max(1, min(25, wps))
            self.config.set("stream_reveal_wps", wps)
            self.config.save()
            self.visualizer.set_stream_reveal_wps(wps)
        elif key == "stream_catch_up_enabled":
            enabled = bool(value)
            self.config.set("stream_catch_up_enabled", enabled)
            self.config.save()
            self.visualizer.set_stream_catch_up_enabled(enabled)
        elif key in {
            "use_antigravity_proxy_search",
            "antigravity_proxy_url",
            "antigravity_api_key",
            "antigravity_search_model",
            "antigravity_search_fallback_model",
            "antigravity_thinking_level",
        }:
            self.config.set(key, value)
            self.config.save()
            self.search_client.update_config(
                base_url=self.config.get("antigravity_proxy_url", "http://127.0.0.1:8045"),
                api_key=self.config.get("antigravity_api_key", ""),
                primary_model=self.config.get("antigravity_search_model", "gemini-3-flash"),
                fallback_model=self.config.get(
                    "antigravity_search_fallback_model", "gemini-2.5-flash"
                ),
                thinking_level=self.config.get("antigravity_thinking_level", "high"),
            )

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
            trace_widget_event(
                "widget_state_request",
                trigger="controller.set_recording",
                reason="recording started",
                recording=recording,
                mode=mode,
                widget_mode="listening",
            )
            self._search_stream_started = False
            self.recording_mode = mode
            self.visualizer.set_listening_mode(reason=f"recording started ({mode})")
            # Show first, then position - some window systems reset position during show()
            self.visualizer.show()
            self._position_visualizer_at_cursor()
            self.recorder.start_recording()
        else:
            # Keep visualizer visible and switch to a processing animation
            # while the API request and transcription are in progress.
            trace_widget_event(
                "widget_state_request",
                trigger="controller.set_recording",
                reason="recording stopped; request pipeline pending",
                recording=recording,
                mode=self.recording_mode,
                widget_mode="processing",
            )
            self.visualizer.set_processing_mode(
                "Processing",
                reason="recording stopped; awaiting API pipeline",
            )
            self.recorder.stop_recording()

    def _on_search_progress(self, text: str) -> None:
        cleaned = " ".join(str(text or "").split()).strip()
        if not cleaned:
            return
        if cleaned.lower() == "refining query":
            trace_widget_event(
                "widget_step_signal_skipped",
                trigger="controller._on_search_progress",
                reason="refining query step hidden in compact widget",
                step=cleaned,
            )
            return
        trace_widget_event(
            "widget_step_signal",
            trigger="controller._on_search_progress",
            reason="SearchWorker.progress signal",
            step=cleaned,
        )
        self.visualizer.set_processing_step(
            cleaned,
            reason="SearchWorker.progress signal",
        )

    def _on_search_stream_text(self, rendered_text: str) -> None:
        text = str(rendered_text or "")
        if not text:
            return
        if not self._search_stream_started:
            self._search_stream_started = True
            trace_widget_event(
                "widget_stream_started",
                trigger="controller._on_search_stream_text",
                reason="first streamed answer chunk received",
            )
            self.visualizer.begin_streaming_answer(reason="first streamed answer chunk")
        self.visualizer.update_streaming_answer(
            text,
            reason="proxy streamed answer chunk",
        )

    def _show_proxy_required_notice(self) -> None:
        notice = "Antigravity proxy needed for image context answer."
        self.window.update_log(notice)
        self.visualizer.set_processing_step(
            "Antigravity proxy needed",
            reason="image answer attempted while proxy search disabled",
        )
        QTimer.singleShot(
            1600,
            lambda: self.visualizer.cancel_processing(
                reason="proxy required for image answer mode"
            ),
        )

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

    def _capture_selected_text(self, timeout_sec: float = 0.22) -> str:
        """
        Best-effort selected-text capture from the active app.

        Strategy:
        1) Backup clipboard text
        2) Send Ctrl+C to copy current selection
        3) Read copied text if clipboard changed
        4) Restore clipboard text
        """
        original_clipboard: Optional[str] = None
        before_normalized = ""

        try:
            original_clipboard = pyperclip.paste()
            before_normalized = " ".join(str(original_clipboard or "").split()).strip()
        except Exception:
            original_clipboard = None

        try:
            keyboard.send("ctrl+c")
        except Exception as exc:
            logger.debug("Selection capture skipped: failed to send Ctrl+C (%s)", exc)
            return ""

        deadline = time.time() + max(0.08, float(timeout_sec))
        captured = ""
        while time.time() < deadline:
            time.sleep(0.03)
            try:
                current_clip = pyperclip.paste()
            except Exception:
                continue

            normalized = " ".join(str(current_clip or "").split()).strip()
            if not normalized:
                continue
            if normalized != before_normalized:
                captured = normalized
                break

        if original_clipboard is not None:
            try:
                pyperclip.copy(original_clipboard)
            except Exception as exc:
                logger.debug("Selection capture: clipboard restore skipped (%s)", exc)

        if len(captured) > 280:
            captured = captured[:277] + "..."
        return captured

    def _capture_screen_region_png(self, max_edge: int = 1400) -> Optional[bytes]:
        """Open a crosshair selector and return selected image region as PNG bytes."""
        screen = self.app.screenAt(QCursor.pos())
        if screen is None:
            screen = self.app.primaryScreen()
        if screen is None:
            logger.warning("Image context capture skipped: no available screen.")
            return None

        screens = self.app.screens()
        selector = ScreenRegionSelector(screens=screens, preferred_screen=screen, parent=None)
        if selector.exec() != int(QDialog.DialogCode.Accepted):
            return None

        pixmap = selector.selected_pixmap()
        if pixmap.isNull():
            return None

        width = pixmap.width()
        height = pixmap.height()
        max_dim = max(width, height)
        if max_dim > max(300, int(max_edge)):
            scaled_w = max(1, int(round(width * float(max_edge) / float(max_dim))))
            scaled_h = max(1, int(round(height * float(max_edge) / float(max_dim))))
            pixmap = pixmap.scaled(
                scaled_w,
                scaled_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        blob = QByteArray()
        buffer = QBuffer(blob)
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            return None
        ok = pixmap.save(buffer, "PNG")
        buffer.close()
        if not ok:
            return None
        return bytes(blob)

    def start_transcription(self, audio_source: Any) -> None:
        """Start transcription. audio_source can be BytesIO buffer or file path."""
        self.window.update_log(f"Processing ({self.recording_mode})...")

        # Get common config
        use_fmt = self.config.get("use_formatter")
        fmt_model = self.config.get("formatter_model", "openai/gpt-oss-120b") # Default if missing

        if self.recording_mode in {"search", "search_image"}:
            # Quick Answer Mode
            use_proxy_search = bool(self.config.get("use_antigravity_proxy_search", False))
            self._search_stream_started = False
            if self.recording_mode == "search_image":
                if not use_proxy_search:
                    self._show_proxy_required_notice()
                    return
                self._start_image_search_pipeline(audio_source, fmt_model, use_proxy_search)
                return

            self.visualizer.set_processing_step(
                "Transcribing speech",
                reason="search mode entered transcription phase",
            )
            selected_text = self._capture_selected_text()
            provider_name = "Antigravity Proxy" if use_proxy_search else "Groq Compound"
            logger.info(
                "Starting Quick Answer search (Provider: %s, Refiner: %s, SelectedContext: %s, ImageContext: no)...",
                provider_name,
                fmt_model,
                "yes" if selected_text else "no",
            )
            # Reuse the formatter model (High Intelligence) for refinement
            self.worker = SearchWorker(
                self.groq,
                audio_source,
                refinement_model_id=fmt_model,
                search_client=self.search_client if use_proxy_search else None,
                selected_text=selected_text,
            )
            self.worker.progress.connect(self._search_progress_signal.emit)
            self.worker.stream_text.connect(self._on_search_stream_text)
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

    def _start_image_search_pipeline(
        self,
        audio_source: Any,
        refinement_model_id: str,
        use_proxy_search: bool,
    ) -> None:
        """Search-image mode: first transcribe speech, then capture image context."""
        self.visualizer.set_processing_step(
            "Transcribing speech",
            reason="image-search mode transcription phase",
        )
        self.window.update_log("Detecting speech for image context...")
        self.worker = TranscriptionWorker(
            self.groq,
            audio_source,
            use_formatter=False,
            format_model=refinement_model_id,
        )
        self.worker.finished.connect(
            lambda raw_text, _final_text: self._continue_image_search_pipeline(
                raw_text,
                refinement_model_id,
                use_proxy_search,
            )
        )
        self.worker.error.connect(self.show_error)
        self.worker.start()

    def _continue_image_search_pipeline(
        self,
        raw_text: str,
        refinement_model_id: str,
        use_proxy_search: bool,
    ) -> None:
        """Continue search-image mode once speech has been transcribed."""
        query_text = (raw_text or "").strip()
        if not query_text:
            self.show_error("No speech detected.")
            return

        self.visualizer.set_processing_step(
            "Waiting for image selection",
            reason="transcription complete; waiting for image selection",
        )
        self.window.update_log("Select an on-screen region for image context...")
        image_png_bytes = self._capture_screen_region_png()
        if image_png_bytes is None:
            self.window.update_log("Image context selection canceled.")
            self.visualizer.cancel_processing(reason="image selection canceled")
            return

        use_proxy_for_request = use_proxy_search or (image_png_bytes is not None)
        provider_name = "Antigravity Proxy" if use_proxy_for_request else "Groq Compound"
        logger.info(
            "Starting Quick Answer search (Provider: %s, Refiner: %s, SelectedContext: no, ImageContext: yes)...",
            provider_name,
            refinement_model_id,
        )
        self.worker = SearchWorker(
            self.groq,
            None,
            refinement_model_id=refinement_model_id,
            search_client=self.search_client if use_proxy_for_request else None,
            query_text=query_text,
            image_png_bytes=image_png_bytes,
        )
        self.worker.progress.connect(self._search_progress_signal.emit)
        self.worker.stream_text.connect(self._on_search_stream_text)
        self.worker.finished.connect(self.on_search_complete)
        self.worker.error.connect(self.show_error)
        self.worker.start()

    def on_transcription_complete(self, raw: str, final: str) -> None:
        self.window.update_log("Transcription complete")
        self.paste_text(final)

    def on_search_complete(self, answer: str) -> None:
        cleaned_answer = (answer or "").strip() or "No answer available."
        self.window.update_log(f"Answer: {cleaned_answer}")
        trace_widget_event(
            "widget_answer_ready",
            trigger="controller.on_search_complete",
            reason="search pipeline returned final answer",
            answer_preview=cleaned_answer[:120],
        )
        if self._search_stream_started:
            self.visualizer.complete_streaming_answer(
                cleaned_answer,
                reason="search pipeline completed after streaming",
            )
        else:
            if self.visualizer.is_stream_realtime_enabled():
                self.visualizer.show_answer(
                    cleaned_answer,
                    reason="search pipeline completed",
                )
            else:
                # No live chunks arrived, but paced mode should still reveal the
                # final answer at the configured words/sec.
                self.visualizer.begin_streaming_answer(
                    reason="search pipeline completed without live stream",
                )
                self.visualizer.complete_streaming_answer(
                    cleaned_answer,
                    reason="search pipeline completed without live stream",
                )
        self._search_stream_started = False



    def _snapshot_clipboard_payload(self) -> dict[str, bytes]:
        """Capture clipboard MIME payload so we can restore exactly after paste."""
        try:
            clipboard = self.app.clipboard()
            mime = clipboard.mimeData()
            if mime is None:
                return {}
            payload: dict[str, bytes] = {}
            for fmt in mime.formats():
                payload[str(fmt)] = bytes(mime.data(fmt))
            return payload
        except Exception as exc:
            logger.debug("Clipboard snapshot skipped: %s", exc)
            return {}

    @staticmethod
    def _win32_alloc_hglobal(data: bytes) -> int:
        """Allocate and populate an HGLOBAL block for SetClipboardData."""
        gmem_moveable = 0x0002
        gmem_zeroinit = 0x0040
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_int
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.restype = ctypes.c_void_p

        handle = kernel32.GlobalAlloc(gmem_moveable | gmem_zeroinit, max(1, len(data)))
        if not handle:
            return 0

        locked = kernel32.GlobalLock(handle)
        if not locked:
            kernel32.GlobalFree(handle)
            return 0
        try:
            ctypes.memmove(locked, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)
        return int(handle)

    def _set_clipboard_text_win32(self, text: str, exclude_history: bool = True) -> bool:
        """Write clipboard text via Win32 so we can mark it as excluded from history."""
        if sys.platform != "win32":
            return False

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        cf_unicodetext = 13
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_int
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = ctypes.c_int
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
        user32.RegisterClipboardFormatW.restype = ctypes.c_uint
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = ctypes.c_int
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.restype = ctypes.c_void_p
        if hasattr(kernel32, "GetLastError"):
            kernel32.GetLastError.argtypes = []
            kernel32.GetLastError.restype = ctypes.c_uint

        opened = False
        for _ in range(60):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.01)
        if not opened:
            last_err = int(kernel32.GetLastError()) if hasattr(kernel32, "GetLastError") else 0
            logger.debug("Win32 clipboard write failed: OpenClipboard timed out (GetLastError=%s)", last_err)
            return False

        try:
            if not user32.EmptyClipboard():
                last_err = int(kernel32.GetLastError()) if hasattr(kernel32, "GetLastError") else 0
                logger.debug("Win32 clipboard write failed: EmptyClipboard failed (GetLastError=%s)", last_err)
                return False

            encoded = str(text or "").encode("utf-16-le") + b"\x00\x00"
            text_handle = self._win32_alloc_hglobal(encoded)
            if not text_handle:
                logger.debug("Win32 clipboard write failed: GlobalAlloc for CF_UNICODETEXT returned null")
                return False
            if not user32.SetClipboardData(cf_unicodetext, text_handle):
                kernel32.GlobalFree(text_handle)
                last_err = int(kernel32.GetLastError()) if hasattr(kernel32, "GetLastError") else 0
                logger.debug("Win32 clipboard write failed: SetClipboardData(CF_UNICODETEXT) failed (GetLastError=%s)", last_err)
                return False

            if exclude_history:
                # Microsoft-documented formats for clipboard history/cloud behavior.
                flags: list[tuple[str, int]] = [
                    ("ExcludeClipboardContentFromMonitorProcessing", 1),
                    ("CanIncludeInClipboardHistory", 0),
                    ("CanUploadToCloudClipboard", 0),
                ]
                for format_name, value in flags:
                    fmt = user32.RegisterClipboardFormatW(format_name)
                    if not fmt:
                        continue
                    value_handle = self._win32_alloc_hglobal(int(value).to_bytes(4, "little", signed=False))
                    if not value_handle:
                        continue
                    if not user32.SetClipboardData(fmt, value_handle):
                        kernel32.GlobalFree(value_handle)
            return True
        except Exception as exc:
            logger.debug("Win32 clipboard write failed: %s", exc)
            return False
        finally:
            user32.CloseClipboard()

    def _set_clipboard_text(self, text: str) -> bool:
        cleaned = str(text or "")
        if sys.platform == "win32":
            # On Windows, keep staging history-safe only. If Win32 staging fails,
            # fail the paste instead of leaking staged text into Win+V history.
            return self._set_clipboard_text_win32(cleaned, exclude_history=True)

        if self._set_clipboard_text_win32(cleaned, exclude_history=True):
            return True

        try:
            self.app.clipboard().setText(cleaned)
            return True
        except Exception as exc:
            logger.debug("Qt clipboard setText failed: %s", exc)

        try:
            pyperclip.copy(cleaned)
            return True
        except Exception as exc:
            logger.debug("pyperclip fallback setText failed: %s", exc)
            return False

    def _restore_clipboard_payload(self, payload: dict[str, bytes], fallback_text: str = "") -> bool:
        # Try lossless MIME restore first.
        try:
            clipboard = self.app.clipboard()
            if payload:
                mime = QMimeData()
                for fmt, data in payload.items():
                    mime.setData(str(fmt), QByteArray(data))
                clipboard.setMimeData(mime)
                return True
        except Exception as exc:
            logger.debug("Clipboard restore failed: %s", exc)
        # Fallback to restoring plain text (still excluded from history on Win32 path).
        try:
            if self._set_clipboard_text_win32(str(fallback_text or ""), exclude_history=True):
                return True
        except Exception:
            pass
        try:
            clipboard = self.app.clipboard()
            if fallback_text:
                clipboard.setText(str(fallback_text))
            else:
                clipboard.clear()
            return True
        except Exception:
            pass
        try:
            pyperclip.copy(str(fallback_text or ""))
            return True
        except Exception:
            return False

    def _schedule_clipboard_restore(
        self,
        payload: dict[str, bytes],
        fallback_text: str = "",
        initial_delay_ms: int = 550,
    ) -> None:
        delays_ms = [max(40, int(initial_delay_ms)), 250, 250]

        def _attempt(index: int = 0) -> None:
            if self._restore_clipboard_payload(payload, fallback_text=fallback_text):
                logger.debug("Clipboard restored after ghost paste")
                return
            next_index = index + 1
            if next_index >= len(delays_ms):
                logger.debug("Clipboard restore skipped after retries")
                return
            QTimer.singleShot(delays_ms[next_index], lambda idx=next_index: _attempt(idx))

        QTimer.singleShot(delays_ms[0], lambda: _attempt(0))

    def paste_text(self, text: str) -> None:
        """Ghost paste: backup clipboard, paste text, restore original clipboard."""
        cleaned_text = str(text or "").strip()
        if not cleaned_text:
            # Nothing to paste — surface failure so the visualizer exits processing state.
            self._paste_failed_signal.emit()
            return

        # Clipboard path: temporary clipboard + Ctrl+V, then restore original clipboard.
        clipboard_payload = self._snapshot_clipboard_payload()
        try:
            clipboard_text_fallback = str(self.app.clipboard().text() or "")
        except Exception:
            try:
                clipboard_text_fallback = str(pyperclip.paste() or "")
            except Exception:
                clipboard_text_fallback = ""

        try:
            if not self._set_clipboard_text(cleaned_text):
                raise RuntimeError("Unable to stage transcription text in clipboard")
            time.sleep(0.06)
            keyboard.send('ctrl+v')
        except Exception as exc:
            logger.error("Clipboard paste failed: %s", exc)
            self._schedule_clipboard_restore(
                clipboard_payload,
                fallback_text=clipboard_text_fallback,
                initial_delay_ms=60,
            )
            self._paste_failed_signal.emit()
            return

        # Emit completion only after ctrl+v has been dispatched successfully.
        self._paste_completed_signal.emit()
        self._schedule_clipboard_restore(
            clipboard_payload,
            fallback_text=clipboard_text_fallback,
            initial_delay_ms=550,
        )

    def _on_paste_completed(self) -> None:
        trace_widget_event(
            "widget_completion_signal",
            trigger="controller._on_paste_completed",
            reason="paste pipeline completed successfully",
        )
        self.visualizer.play_completion_and_hide(reason="paste completed")

    def _on_paste_failed(self) -> None:
        trace_widget_event(
            "widget_completion_signal",
            trigger="controller._on_paste_failed",
            reason="paste pipeline failed",
        )
        self.visualizer.cancel_processing(reason="paste failed")

    def show_error(self, msg: str) -> None:
        self.window.update_log(f"Error: {msg}")
        self._search_stream_started = False
        trace_widget_event(
            "widget_error",
            trigger="controller.show_error",
            reason="error surfaced to UI",
            message=str(msg)[:180],
        )
        self.visualizer.cancel_processing(reason=f"error: {str(msg)[:120]}")
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

        # Stop and join any active worker thread before tearing down the event loop.
        if self.worker is not None:
            try:
                self.worker.quit()
                if not self.worker.wait(3000):  # up to 3 s
                    logger.warning("Worker thread did not exit cleanly; terminating.")
                    self.worker.terminate()
                    self.worker.wait(1000)
            except Exception as exc:
                logger.debug("Error stopping worker on quit: %s", exc)
            finally:
                self.worker = None

        # Stop hotkey listener
        self.hotkey_mgr.stop_listening()
        self.search_hotkey.stop_listening()
        self.image_search_hotkey.stop_listening()

        # Hide tray icon
        self.tray_icon.hide()

        # Close windows
        self.window.close()
        self.visualizer.close()

        # Quit the application
        self.app.quit()

    def run(self) -> None:
        sys.exit(self.app.exec())
