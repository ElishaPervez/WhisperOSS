import sys
import threading
import time
import keyboard
import pyperclip
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu, QInputDialog
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QAction, QCursor


from src.config_manager import ConfigManager
from src.audio_recorder import AudioRecorder
from src.groq_client import GroqClient
from src.hotkey_manager import HotkeyManager
from src.ui_main_window import MainWindow
from src.ui_visualizer import AudioVisualizer

# Configure logger
logger = logging.getLogger(__name__)

# Worker Thread for API calls to prevent UI freezing
class TranscriptionWorker(QThread):
    finished = pyqtSignal(str, str) # raw_text, final_text
    error = pyqtSignal(str)

    def __init__(self, groq_client, audio_file, use_formatter, format_model, 
                 use_translation=False, target_language="English", formatting_style="Default"):
        super().__init__()
        self.groq_client = groq_client
        self.audio_file = audio_file
        self.use_formatter = use_formatter
        self.format_model = format_model
        self.use_translation = use_translation
        self.target_language = target_language
        self.formatting_style = formatting_style

    def run(self):
        try:
            # Step 1: Transcribe with prompt for better accuracy
            from src.prompts import TRANSCRIPTION_PROMPT
            raw_text = self.groq_client.transcribe(self.audio_file, prompt=TRANSCRIPTION_PROMPT)
            final_text = raw_text

            # Step 2: Format / Translate (Optional)
            if self.use_formatter:
                if self.use_translation:
                    from src.prompts import SYSTEM_PROMPT_TRANSLATOR
                    prompt = SYSTEM_PROMPT_TRANSLATOR.format(language=self.target_language)
                    logger.info(f"Using Translator Prompt for language: {self.target_language}")
                    formatted = self.groq_client.format_text(raw_text, self.format_model, system_prompt=prompt)
                else:
                    from src.prompts import get_formatter_prompt
                    prompt = get_formatter_prompt(self.formatting_style)
                    logger.info(f"Using Formatter Prompt for style: {self.formatting_style}")
                    formatted = self.groq_client.format_text(raw_text, self.format_model, system_prompt=prompt)
                
                final_text = formatted

            self.finished.emit(raw_text, final_text)

        except Exception as e:
            logger.error(f"TranscriptionWorker error: {e}")
            self.error.emit(str(e))

class WhisperAppController(QObject):
    # Thread-safe signals for hotkey events
    _start_recording_signal = pyqtSignal()
    _stop_recording_signal = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False) # Keep running for system tray

        # Load config first
        self.config = ConfigManager()
        
        # Connect hotkey signals to recording actions (thread-safe)
        self._start_recording_signal.connect(lambda: self.set_recording(True))
        self._stop_recording_signal.connect(lambda: self.set_recording(False))
        
        # Check for first run (no API key) and prompt before initializing
        self._check_first_run_api_key()
        self.groq = GroqClient(self.config.get("api_key"))
        self.recorder = AudioRecorder(self.config.get("input_device_index"))
        self.hotkey_mgr = HotkeyManager(
            modifiers=['ctrl'],
            trigger_key='win',
            on_start=self._start_recording_signal.emit,
            on_stop=self._stop_recording_signal.emit
        )
        
        # UI
        self.window = MainWindow(self.config)
        self.visualizer = AudioVisualizer()
        
        # System Tray
        self.setup_system_tray()
        
        # Override window close to minimize to tray
        self.window.closeEvent = self.on_window_close

        # Connections
        self.connect_signals()
        self.init_state()

    def _check_first_run_api_key(self):
        """Prompt for API key on first run before full initialization"""
        api_key = self.config.get("api_key", "")
        
        if not api_key or api_key.strip() == "":
            # Show welcome message and prompt for API key
            msg = QMessageBox()
            msg.setWindowTitle("Welcome to WhisperOSS")
            msg.setText("Welcome to WhisperOSS!\n\nThis app requires a Groq API key to transcribe audio.\nPlease enter your API key to continue.")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
            # Keep prompting until valid key or user cancels
            while True:
                text, ok = QInputDialog.getText(
                    None, 
                    "Groq API Key Required", 
                    "Enter your Groq API Key:\n(Get one at https://console.groq.com)",
                    text=""
                )
                
                if ok and text.strip():
                    # Save the API key
                    self.config.set("api_key", text.strip())
                    self.config.save()
                    break
                elif not ok:
                    # User cancelled - show warning and exit
                    warn = QMessageBox()
                    warn.setWindowTitle("API Key Required")
                    warn.setText("WhisperOSS requires an API key to function.\nThe application will now exit.")
                    warn.setIcon(QMessageBox.Icon.Warning)
                    warn.exec()
                    sys.exit(0)
                else:
                    # Empty key entered, prompt again
                    QMessageBox.warning(None, "Invalid Key", "Please enter a valid API key.")

    def connect_signals(self):
        # UI -> Logic
        self.window.record_toggled.connect(self.set_recording)
        self.window.config_changed.connect(self.on_config_changed)
        
        # Recorder -> Floating visualizer overlay
        self.recorder.visualizer_update.connect(self.visualizer.update_level)
        self.recorder.recording_finished.connect(self.start_transcription)
        self.recorder.error_occurred.connect(self.show_error)

    def init_state(self):
        # Populate Devices
        devices = self.recorder.list_devices()
        self.window.set_device_list(devices)

        # Populate Models (Async preferred but sync for init is ok)
        self.refresh_models()
        
        # Start global listener
        self.hotkey_mgr.start_listening()

        # Show Windows
        self.window.show()
        # self.visualizer.show() # Hidden by default, shown on record
        # Visualizer positioning is now dynamic based on cursor location

    def on_config_changed(self, key, value):
        if key == "api_key":
            self.groq.update_api_key(value)
            self.refresh_models()
        elif key == "input_device_index":
            self.recorder.update_device(value)

    def refresh_models(self):
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

    def toggle_recording(self):
        # Toggle state
        is_rec = not self.recorder.is_recording
        self.set_recording(is_rec)

    def set_recording(self, recording):
        # Update UI state (thread-safe signal)
        self.window.set_recording_state(recording)
        
        if recording:
            # Show first, then position - some window systems reset position during show()
            self.visualizer.show()
            self._position_visualizer_at_cursor()
            self.recorder.start_recording()
        else:
            self.visualizer.hide()
            self.recorder.stop_recording()
    
    def _position_visualizer_at_cursor(self):
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

    def start_transcription(self, file_path):
        self.window.update_log("Transcribing...")
        
        use_fmt = self.config.get("use_formatter")
        fmt_model = self.config.get("formatter_model")
        use_trans = self.config.get("translation_enabled")
        target_lang = self.config.get("target_language")
        fmt_style = self.config.get("formatting_style", "Default")

        logger.info(f"Starting transcription: fmt={use_fmt}, trans={use_trans}, lang={target_lang}, style={fmt_style}")

        self.worker = TranscriptionWorker(
            self.groq, file_path, use_fmt, fmt_model, 
            use_translation=use_trans, target_language=target_lang,
            formatting_style=fmt_style
        )
        self.worker.finished.connect(self.on_transcription_complete)
        self.worker.error.connect(self.show_error)
        self.worker.start()

    def on_transcription_complete(self, raw, final):
        self.window.update_log(f"Raw: {raw}\n\nFinal:\n{final}")
        self.paste_text(final)

    def paste_text(self, text):
        try:
            # Strip leading/trailing whitespace before pasting
            pyperclip.copy(text.strip())
            # Give the clipboard a moment to settle using non-blocking delay if possible, 
            # or just simple sleep since we are in main thread but operation is fast.
            time.sleep(0.1) 
            keyboard.send('ctrl+v')
        except Exception as e:
            self.show_error(f"Paste Failed: {e}")

    def show_error(self, msg):
        self.window.update_log(f"Error: {msg}")
        # Optional: QMessageBox.critical(self.window, "Error", msg)

    def setup_system_tray(self):
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
    
    def on_tray_activated(self, reason):
        """Handle tray icon activation (left or right click)"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left click
            self.show_window()
        elif reason == QSystemTrayIcon.ActivationReason.Context:  # Right click
            # Context menu is shown automatically
            pass
    
    def show_window(self):
        """Show and raise the main window"""
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()
    
    def on_window_close(self, event):
        """Hide to system tray instead of closing"""
        event.ignore()
        self.window.hide()
        self.tray_icon.showMessage(
            "WhisperOSS",
            "Application minimized to system tray. Right-click or left-click to restore.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )
    
    def quit_application(self):
        """Properly quit the application, stopping all threads"""
        # Stop recording if active
        if self.recorder.is_recording:
            self.recorder.stop_recording()
        
        # Stop hotkey listener
        self.hotkey_mgr.stop_listening()
        
        # Hide tray icon
        self.tray_icon.hide()
        
        # Close windows
        self.window.close()
        self.visualizer.close()
        
        # Quit the application
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())
