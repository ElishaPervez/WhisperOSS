import keyboard
import logging
import threading
import time

class HotkeyManager:
    """
    Hotkey manager with hold-to-record behavior.
    Uses a polling approach to reliably detect when keys are released,
    since Windows key release events can be inconsistent.
    """
    def __init__(
        self,
        modifiers=None,
        trigger_key='win',
        on_start=None,
        on_stop=None,
        callback=None,
        forbidden_keys=None,
        activation_delay_ms: int = 0,
    ):
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
        self._activation_pending = False
        self.forbidden_keys = list(forbidden_keys or [])
        try:
            self.activation_delay_ms = max(0, int(activation_delay_ms))
        except Exception:
            self.activation_delay_ms = 0
        
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

    def _check_forbidden(self):
        """Check that forbidden keys are NOT currently pressed."""
        for key_name in self.forbidden_keys:
            try:
                if keyboard.is_pressed(key_name):
                    return False
            except Exception:
                continue
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
            if self._check_modifiers() and self._check_forbidden() and not self.is_active and not self._activation_pending:
                if self.activation_delay_ms <= 0:
                    self._activate_hotkey()
                    return

                self._activation_pending = True

                def delayed_activation():
                    time.sleep(self.activation_delay_ms / 1000.0)
                    if not self.is_listening or self.is_active:
                        self._activation_pending = False
                        return
                    if self._is_trigger_pressed() and self._check_modifiers() and self._check_forbidden():
                        self._activate_hotkey()
                    else:
                        self._activation_pending = False

                threading.Thread(target=delayed_activation, daemon=True).start()

    def _activate_hotkey(self):
        """Activate hotkey and emit start callback once."""
        if self.is_active:
            return
        self.is_active = True
        self._activation_pending = False
        hotkey_str = f"{'+'.join(self.modifiers)}+{self.trigger_key}"
        logging.info("Hotkey activated: %s held", hotkey_str)
        if self.on_start:
            self.on_start()
        elif self.callback:
            self.callback()
        self._start_release_polling()

    def _start_release_polling(self):
        """Start polling to detect when keys are released."""

        def poll_loop():
            while self.is_active and self.is_listening:
                time.sleep(0.05)  # Poll every 50ms
                # Check if EITHER the trigger OR modifiers are released
                if not self._is_trigger_pressed() or not self._check_modifiers() or not self._check_forbidden():
                    if self.is_active:  # Double-check still active
                        self.is_active = False
                        self._activation_pending = False
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
                self._activation_pending = False
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
