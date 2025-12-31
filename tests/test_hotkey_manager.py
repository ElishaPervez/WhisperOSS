import pytest
from unittest.mock import MagicMock, patch
from src.hotkey_manager import HotkeyManager

@pytest.fixture
def mock_keyboard():
    with patch("src.hotkey_manager.keyboard") as mock_kb:
        yield mock_kb

def test_init():
    callback = MagicMock()
    # Updated API: modifiers=['ctrl'], trigger_key='win'
    mgr = HotkeyManager(modifiers=['alt'], trigger_key='x', callback=callback)
    assert mgr.modifiers == ['alt']
    assert mgr.trigger_key == 'x'
    assert mgr.callback == callback
    assert not mgr.is_listening

def test_start_listening(mock_keyboard):
    callback = MagicMock()
    mgr = HotkeyManager(callback=callback)
    mgr.start_listening()
    
    # Updated: Uses on_press instead of add_hotkey
    mock_keyboard.on_press.assert_called_once()
    assert mgr.is_listening

def test_stop_listening(mock_keyboard):
    mgr = HotkeyManager(callback=MagicMock())
    mgr.is_listening = True
    # Mock the internal hook object
    hook_ref = MagicMock()
    mgr._press_hook = hook_ref
    
    mgr.stop_listening()
    
    # Updated: Uses unhook
    mock_keyboard.unhook.assert_called_with(hook_ref)
    assert not mgr.is_listening
    assert mgr._press_hook is None

def test_update_hotkey(mock_keyboard):
    mgr = HotkeyManager(modifiers=['ctrl'], trigger_key='a', callback=MagicMock())
    mgr.is_listening = True
    mgr._press_hook = MagicMock()
    
    # Update
    mgr.update_hotkey(modifiers=['alt'], trigger_key='b')
    
    # Should stop then start
    mock_keyboard.unhook.assert_called()
    mock_keyboard.on_press.assert_called()
    
    assert mgr.modifiers == ['alt']
    assert mgr.trigger_key == 'b'