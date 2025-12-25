import pytest
from unittest.mock import MagicMock, patch
from src.hotkey_manager import HotkeyManager

@pytest.fixture
def mock_keyboard():
    with patch("src.hotkey_manager.keyboard") as mock_kb:
        yield mock_kb

def test_init():
    callback = MagicMock()
    mgr = HotkeyManager(hotkey='alt+x', callback=callback)
    assert mgr.hotkey == 'alt+x'
    assert mgr.callback == callback
    assert not mgr.is_listening

def test_start_listening(mock_keyboard):
    callback = MagicMock()
    mgr = HotkeyManager(callback=callback)
    mgr.start_listening()
    
    mock_keyboard.add_hotkey.assert_called_with('ctrl+shift+space', callback)
    assert mgr.is_listening

def test_stop_listening(mock_keyboard):
    mgr = HotkeyManager(callback=MagicMock())
    mgr.is_listening = True
    mgr.stop_listening()
    
    mock_keyboard.remove_hotkey.assert_called_with('ctrl+shift+space')
    assert not mgr.is_listening

def test_update_hotkey(mock_keyboard):
    mgr = HotkeyManager(hotkey='old', callback=MagicMock())
    mgr.is_listening = True
    
    mgr.update_hotkey('new')
    
    mock_keyboard.remove_hotkey.assert_called_with('old')
    mock_keyboard.add_hotkey.assert_called_with('new', mgr.callback)
    assert mgr.hotkey == 'new'

def test_start_listening_fail(mock_keyboard):
    mock_keyboard.add_hotkey.side_effect = Exception("Fail")
    mgr = HotkeyManager(callback=MagicMock())
    mgr.start_listening()
    assert not mgr.is_listening
