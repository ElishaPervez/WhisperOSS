import sys
from PyQt6.QtWidgets import QApplication
from src.controller import WhisperAppController

if __name__ == "__main__":
    # Ensure QApplication exists before Controller initialization
    app = QApplication(sys.argv)
    
    controller = WhisperAppController()
    controller.run()