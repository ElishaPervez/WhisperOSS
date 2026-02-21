import pytest
from unittest.mock import MagicMock, patch, mock_open
import numpy as np
from PyQt6.QtCore import QObject
from src.audio_recorder import AudioRecorder

@pytest.fixture
def mock_pyaudio():
    with patch("src.audio_recorder.pyaudio.PyAudio") as mock_pa:
        yield mock_pa

def test_init(mock_pyaudio):
    recorder = AudioRecorder()
    assert recorder.is_recording is False
    mock_pyaudio.assert_called_once()

def test_list_devices(mock_pyaudio):
    mock_instance = mock_pyaudio.return_value
    mock_instance.get_host_api_info_by_index.return_value = {'deviceCount': 2}
    
    # We will fix the code to call this once per device, but for safety in tests,
    # we can provide enough side effects or just use a dict/func if needed.
    # But let's assume we refactor the code to call it once.
    mock_instance.get_device_info_by_host_api_device_index.side_effect = [
        {'maxInputChannels': 1, 'name': 'Mic 1'},
        {'maxInputChannels': 0, 'name': 'Speaker 1'}
    ]
    
    recorder = AudioRecorder()
    devices = recorder.list_devices()
    
    assert len(devices) == 1
    assert devices[0] == (0, 'Mic 1')

def test_start_recording_success(mock_pyaudio, qtbot):
    recorder = AudioRecorder()
    mock_instance = mock_pyaudio.return_value
    mock_stream = MagicMock()
    mock_instance.open.return_value = mock_stream
    
    with qtbot.waitSignal(recorder.error_occurred, timeout=100, raising=False) as blocker:
        recorder.start_recording()
    
    assert blocker.signal_triggered is False
    assert recorder.is_recording is True
    mock_stream.start_stream.assert_called_once()

def test_start_recording_fail(mock_pyaudio, qtbot):
    recorder = AudioRecorder()
    mock_instance = mock_pyaudio.return_value
    mock_instance.open.side_effect = Exception("Audio Error")
    
    with qtbot.waitSignal(recorder.error_occurred) as blocker:
        recorder.start_recording()
    
    assert blocker.args[0] == "Failed to start recording: Audio Error"
    assert recorder.is_recording is False

def test_stop_recording_success(mock_pyaudio, qtbot):
    recorder = AudioRecorder()
    recorder.is_recording = True
    mock_stream = MagicMock() # Create local reference
    recorder.stream = mock_stream
    recorder.frames = [b'\x00\x00']
    
    # Mock wave.open to avoid actual WAV processing
    with patch("src.audio_recorder.wave.open") as mock_wave:
        mock_wf = MagicMock()
        mock_wave.return_value = mock_wf
        with qtbot.waitSignal(recorder.recording_finished) as blocker:
            recorder.stop_recording()
    
    assert recorder.is_recording is False
    assert recorder.stream is None # Should be cleared
    
    # Use local reference to verify calls
    mock_stream.stop_stream.assert_called_once()
    mock_stream.close.assert_called_once()
    mock_wave.assert_called_once()
    
    # Now emits BytesIO buffer, not filename (in-memory recording)
    import io
    assert hasattr(blocker.args[0], 'read')  # Should be a file-like object (BytesIO)

def test_audio_callback_visualizer(mock_pyaudio, qtbot):
    recorder = AudioRecorder()
    recorder.is_recording = True
    
    # Generate dummy audio data (sine wave-ish)
    # int16 max is 32767
    data = np.array([1000, 2000, -3000], dtype=np.int16).tobytes()
    
    with qtbot.waitSignal(recorder.visualizer_update) as blocker:
        recorder._audio_callback(data, 1024, None, None)
    
    emitted = blocker.args[0]
    linear = 3000 / 7000.0
    assert 0.0 <= emitted <= 1.0
    # Low/medium volume should now be boosted for better visual responsiveness.
    assert emitted > linear
