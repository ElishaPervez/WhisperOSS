import sys
import os
from pathlib import Path

# Add project root to sys.path to support 'from src.controller ...' imports
# when this file is run directly as a script.
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtWidgets import QApplication
from src.controller import WhisperAppController
from src.debug_trace import configure_debug_trace, trace_widget_event

def main():
    debug_path = configure_debug_trace()
    trace_widget_event(
        "app_startup",
        trigger="main.main",
        reason="application entrypoint invoked",
        debug_path=str(debug_path),
    )

    # Ensure QApplication exists before Controller initialization
    app = QApplication(sys.argv)
    
    controller = WhisperAppController()
    trace_widget_event(
        "controller_ready",
        trigger="main.main",
        reason="controller initialized; entering run loop",
    )
    controller.run()

if __name__ == "__main__":
    main()
