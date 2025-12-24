import sys
import threading
import time
import keyboard
import pyperclip
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from config_manager import ConfigManager
from audio_recorder import AudioRecorder
from groq_client import GroqClient
from hotkey_manager import HotkeyManager
from ui_main_window import MainWindow
from ui_visualizer import AudioVisualizer

# Worker Thread for API calls to prevent UI freezing
class TranscriptionWorker(QThread):
    finished = pyqtSignal(str, str) # raw_text, final_text
    error = pyqtSignal(str)

    def __init__(self, groq_client, audio_file, use_formatter, format_model):
        super().__init__()
        self.groq_client = groq_client
        self.audio_file = audio_file
        self.use_formatter = use_formatter
        self.format_model = format_model

    def run(self):
        try:
            # Step 1: Transcribe
            raw_text = self.groq_client.transcribe(self.audio_file)
            if "Error" in raw_text: # Simple error check
                self.error.emit(raw_text)
                return

            final_text = raw_text

            # Step 2: Format (Optional)
            if self.use_formatter:
                formatted = self.groq_client.format_text(raw_text, self.format_model)
                if "Error" not in formatted:
                    final_text = formatted
            
            self.finished.emit(raw_text, final_text)

        except Exception as e:
            self.error.emit(str(e))

class WhisperApp(QObject):
    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False) # Keep running for hotkeys potentially

        # Components
        self.config = ConfigManager()
        self.groq = GroqClient(self.config.get("api_key"))
        self.recorder = AudioRecorder(self.config.get("input_device_index"))
        self.hotkey_mgr = HotkeyManager(callback=self.toggle_recording)
        
        # UI
        self.window = MainWindow(self.config)
        self.visualizer = AudioVisualizer()

        # Connections
        self.connect_signals()
        self.init_state()

    def connect_signals(self):
        # UI -> Logic
        self.window.record_toggled.connect(self.set_recording)
        self.window.config_changed.connect(self.on_config_changed)
        
        # Recorder -> Floating Visualizer
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
        
        # Position Visualizer at center-bottom of screen
        screen = self.app.primaryScreen().geometry()
        vis_width = self.visualizer.width()
        vis_height = self.visualizer.height()
        x = (screen.width() - vis_width) // 2
        y = screen.height() - vis_height - 60  # 60px from bottom for taskbar
        self.visualizer.move(x, y)

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
            self.visualizer.show()
            self.recorder.start_recording()
        else:
            self.visualizer.hide()
            self.recorder.stop_recording()

    def start_transcription(self, file_path):
        self.window.update_log("Transcribing...")
        
        use_fmt = self.config.get("use_formatter")
        fmt_model = self.config.get("formatter_model")

        self.worker = TranscriptionWorker(self.groq, file_path, use_fmt, fmt_model)
        self.worker.finished.connect(self.on_transcription_complete)
        self.worker.error.connect(self.show_error)
        self.worker.start()

    def on_transcription_complete(self, raw, final):
        self.window.update_log(f"Raw: {raw}\n\nFinal:\n{final}")
        self.paste_text(final)

    def paste_text(self, text):
        try:
            pyperclip.copy(text)
            # Give the clipboard a moment to settle using non-blocking delay if possible, 
            # or just simple sleep since we are in main thread but operation is fast.
            time.sleep(0.1) 
            keyboard.send('ctrl+v')
        except Exception as e:
            self.show_error(f"Paste Failed: {e}")

    def show_error(self, msg):
        self.window.update_log(f"Error: {msg}")
        # Optional: QMessageBox.critical(self.window, "Error", msg)

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    app = WhisperApp()
    app.run()
