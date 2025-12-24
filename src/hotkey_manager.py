import keyboard
import logging

class HotkeyManager:
    def __init__(self, hotkey='ctrl+shift+space', callback=None):
        self.hotkey = hotkey
        self.callback = callback
        self.is_listening = False

    def start_listening(self):
        if not self.is_listening and self.callback:
            try:
                keyboard.add_hotkey(self.hotkey, self.callback)
                self.is_listening = True
                logging.info(f"Global hotkey '{self.hotkey}' registered.")
            except Exception as e:
                logging.error(f"Failed to register hotkey: {e}")

    def stop_listening(self):
        if self.is_listening:
            try:
                keyboard.remove_hotkey(self.hotkey)
                self.is_listening = False
            except Exception as e:
                logging.error(f"Failed to unregister hotkey: {e}")

    def update_hotkey(self, new_hotkey):
        self.stop_listening()
        self.hotkey = new_hotkey
        self.start_listening()
