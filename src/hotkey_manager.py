import keyboard
import logging

class HotkeyManager:
    """
    Hotkey manager with hold-to-record behavior.
    Uses a polling approach to reliably detect when keys are released,
    since Windows key release events can be inconsistent.
    """
    def __init__(self, modifiers=None, trigger_key='win', on_start=None, on_stop=None, callback=None):
        """
        Args:
            modifiers: List of modifier keys that must be held (default: ['ctrl'])
            trigger_key: The main trigger key (default: 'win')
            on_start: Callback when hotkey is pressed (starts recording)
            on_stop: Callback when hotkey is released (stops recording)
            callback: Legacy toggle callback (for backwards compatibility)
        """
        self.modifiers = modifiers or ['ctrl']
        self.trigger_key = trigger_key
        self.on_start = on_start
        self.on_stop = on_stop
        self.callback = callback  # Legacy support
        self.is_listening = False
        self.is_active = False  # Track if hotkey is currently held
        self._press_hook = None
        self._poll_timer = None
        
        # All possible names for the Windows key
        self._win_key_names = ['win', 'windows', 'left windows', 'right windows', 'cmd', 'super']

    def _is_trigger_pressed(self):
        """Check if the trigger key is currently pressed."""
        # For Windows key, check multiple possible names
        if self.trigger_key.lower() in ['win', 'windows']:
            return (keyboard.is_pressed('left windows') or 
                    keyboard.is_pressed('right windows') or
                    keyboard.is_pressed('windows'))
        return keyboard.is_pressed(self.trigger_key)

    def _check_modifiers(self):
        """Check if all required modifier keys are pressed."""
        for mod in self.modifiers:
            if not keyboard.is_pressed(mod):
                return False
        return True

    def _is_trigger_key(self, event_name):
        """Check if the event is for the trigger key."""
        name_lower = event_name.lower()
        # Handle Windows key special cases
        if self.trigger_key.lower() in ['win', 'windows']:
            return name_lower in self._win_key_names
        return name_lower == self.trigger_key.lower()

    def _on_key_press(self, event):
        """Handle key press event."""
        if self._is_trigger_key(event.name):
            if self._check_modifiers() and not self.is_active:
                self.is_active = True
                logging.info(f"Hotkey activated: Ctrl+Win held")
                if self.on_start:
                    self.on_start()
                elif self.callback:
                    self.callback()
                # Start polling for release
                self._start_release_polling()

    def _start_release_polling(self):
        """Start polling to detect when keys are released."""
        import threading
        
        def poll_loop():
            import time
            while self.is_active and self.is_listening:
                time.sleep(0.05)  # Poll every 50ms
                # Check if EITHER the trigger OR modifiers are released
                if not self._is_trigger_pressed() or not self._check_modifiers():
                    if self.is_active:  # Double-check still active
                        self.is_active = False
                        logging.info(f"Hotkey released: stopping recording")
                        if self.on_stop:
                            self.on_stop()
                        elif self.callback:
                            self.callback()
                    break
        
        self._poll_timer = threading.Thread(target=poll_loop, daemon=True)
        self._poll_timer.start()

    def start_listening(self):
        """Start listening for the hotkey combination."""
        if not self.is_listening:
            try:
                self._press_hook = keyboard.on_press(self._on_key_press)
                self.is_listening = True
                hotkey_str = f"{'+'.join(self.modifiers)}+{self.trigger_key}"
                logging.info(f"Global hotkey '{hotkey_str}' registered (hold to record).")
            except Exception as e:
                logging.error(f"Failed to register hotkey: {e}")

    def stop_listening(self):
        """Stop listening for the hotkey combination."""
        if self.is_listening:
            try:
                if self._press_hook:
                    keyboard.unhook(self._press_hook)
                    self._press_hook = None
                self.is_listening = False
                self.is_active = False
            except Exception as e:
                logging.error(f"Failed to unregister hotkey: {e}")

    def update_hotkey(self, modifiers=None, trigger_key=None):
        """Update the hotkey combination."""
        self.stop_listening()
        if modifiers is not None:
            self.modifiers = modifiers
        if trigger_key is not None:
            self.trigger_key = trigger_key
        self.start_listening()
