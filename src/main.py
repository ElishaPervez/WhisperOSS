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

def main():
    # Ensure QApplication exists before Controller initialization
    app = QApplication(sys.argv)
    
    controller = WhisperAppController()
    controller.run()

if __name__ == "__main__":
    main()
