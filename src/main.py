import sys
from PyQt6.QtWidgets import QApplication
from src.controller import WhisperAppController

def main():
    # Ensure QApplication exists before Controller initialization
    app = QApplication(sys.argv)
    
    controller = WhisperAppController()
    controller.run()

if __name__ == "__main__":
    main()
