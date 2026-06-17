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
    # New enumeration walks ALL host APIs via get_host_api_count() and queries
    # each device, storing the GLOBAL device index (device_info["index"]) and
    # labelling the displayed name with the host API.
    mock_instance.get_host_api_count.return_value = 1
    mock_instance.get_host_api_info_by_index.return_value = {
        'deviceCount': 3, 'name': 'Windows WASAPI'
    }

    mock_instance.get_device_info_by_host_api_device_index.side_effect = [
        {'maxInputChannels': 1, 'name': 'Mic 1', 'index': 5},
        Exception("device warming up"),  # bad device is skipped, not fatal
        {'maxInputChannels': 0, 'name': 'Speaker 1', 'index': 7},
    ]

    recorder = AudioRecorder(always_listening=False)
    devices = recorder.list_devices()

    # Only the valid input device survives; bad device skipped, output device ignored.
    assert len(devices) == 1
    assert devices[0] == (5, 'Mic 1 (WASAPI)')

def test_list_devices_dedup_across_host_apis(mock_pyaudio):
    mock_instance = mock_pyaudio.return_value
    mock_instance.get_host_api_count.return_value = 2
    # Same physical mic exposed under both MME and WASAPI (different global
    # indices). The WASAPI entry is preferred; the MME duplicate collapses away.
    mock_instance.get_host_api_info_by_index.side_effect = [
        {'deviceCount': 1, 'name': 'MME'},
        {'deviceCount': 1, 'name': 'Windows WASAPI'},
    ]
    mock_instance.get_device_info_by_host_api_device_index.side_effect = [
        {'maxInputChannels': 2, 'name': 'Mic A', 'index': 8},   # MME copy
        {'maxInputChannels': 2, 'name': 'Mic A', 'index': 3},   # WASAPI copy
    ]

    recorder = AudioRecorder(always_listening=False)
    devices = recorder.list_devices()

    # One entry, the preferred WASAPI index/label.
    assert devices == [(3, 'Mic A (WASAPI)')]

def test_list_devices_collapses_truncated_mme_name(mock_pyaudio):
    mock_instance = mock_pyaudio.return_value
    mock_instance.get_host_api_count.return_value = 2
    mock_instance.get_host_api_info_by_index.side_effect = [
        {'deviceCount': 1, 'name': 'Windows WASAPI'},
        {'deviceCount': 1, 'name': 'MME'},
    ]
    # MME truncates the long name; it must still collapse onto the full WASAPI one.
    mock_instance.get_device_info_by_host_api_device_index.side_effect = [
        {'maxInputChannels': 1, 'name': 'Microphone (NVIDIA Broadcast)', 'index': 4},
        {'maxInputChannels': 1, 'name': 'Microphone (NVIDIA Broadca', 'index': 9},
    ]

    recorder = AudioRecorder(always_listening=False)
    devices = recorder.list_devices()

    assert devices == [(4, 'Microphone (NVIDIA Broadcast) (WASAPI)')]

def test_list_devices_keeps_distinct_devices(mock_pyaudio):
    mock_instance = mock_pyaudio.return_value
    mock_instance.get_host_api_count.return_value = 1
    mock_instance.get_host_api_info_by_index.return_value = {
        'deviceCount': 2, 'name': 'Windows WASAPI'
    }
    mock_instance.get_device_info_by_host_api_device_index.side_effect = [
        {'maxInputChannels': 1, 'name': 'Realtek Microphone Array', 'index': 1},
        {'maxInputChannels': 1, 'name': 'NVIDIA Broadcast Microphone', 'index': 2},
    ]

    recorder = AudioRecorder(always_listening=False)
    devices = recorder.list_devices()

    # Genuinely different mics are NOT merged.
    assert devices == [
        (1, 'Realtek Microphone Array (WASAPI)'),
        (2, 'NVIDIA Broadcast Microphone (WASAPI)'),
    ]

def test_capture_uses_device_native_sample_rate(mock_pyaudio):
    # WASAPI devices (e.g. NVIDIA Broadcast) reject 16 kHz; we must open at the
    # device's native rate instead of a hardcoded 16000 (fixes Errno -9997).
    mock_instance = mock_pyaudio.return_value
    mock_instance.open.return_value = MagicMock()
    mock_instance.get_device_info_by_index.return_value = {'defaultSampleRate': 48000.0}

    recorder = AudioRecorder(input_device_index=2, always_listening=True)
    recorder.start_listening()

    _, kwargs = mock_instance.open.call_args
    assert kwargs.get('rate') == 48000
    assert recorder._capture_rate == 48000

def test_wav_written_at_capture_rate(mock_pyaudio, qtbot):
    recorder = AudioRecorder(always_listening=False)
    recorder._capture_rate = 44100  # simulate a device captured at 44.1 kHz
    recorder.is_recording = True
    recorder.stream = MagicMock()
    recorder.frames = [b'\x00\x00']

    with patch("src.audio_recorder.wave.open") as mock_wave:
        mock_wf = MagicMock()
        mock_wave.return_value = mock_wf
        with qtbot.waitSignal(recorder.recording_finished):
            recorder.stop_recording()

    # WAV header must match the rate we actually captured at.
    mock_wf.setframerate.assert_called_once_with(44100)

def test_start_recording_success(mock_pyaudio, qtbot):
    # Legacy path: opens a fresh stream on record.
    recorder = AudioRecorder(always_listening=False)
    mock_instance = mock_pyaudio.return_value
    mock_stream = MagicMock()
    mock_instance.open.return_value = mock_stream

    with qtbot.waitSignal(recorder.error_occurred, timeout=100, raising=False) as blocker:
        recorder.start_recording()

    assert blocker.signal_triggered is False
    assert recorder.is_recording is True
    mock_instance.open.assert_called_once()
    mock_stream.start_stream.assert_called_once()

def test_start_recording_fail(mock_pyaudio, qtbot):
    recorder = AudioRecorder(always_listening=False)
    mock_instance = mock_pyaudio.return_value
    mock_instance.open.side_effect = Exception("Audio Error")

    with qtbot.waitSignal(recorder.error_occurred) as blocker:
        recorder.start_recording()

    assert blocker.args[0] == "Failed to start recording: Audio Error"
    assert recorder.is_recording is False

def test_stop_recording_success(mock_pyaudio, qtbot):
    # Legacy path: stream is closed and cleared on stop.
    recorder = AudioRecorder(always_listening=False)
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

def test_start_listening_opens_persistent_stream(mock_pyaudio):
    recorder = AudioRecorder(always_listening=True)
    mock_instance = mock_pyaudio.return_value
    mock_stream = MagicMock()
    mock_instance.open.return_value = mock_stream

    recorder.start_listening()
    assert recorder.stream is mock_stream
    mock_stream.start_stream.assert_called_once()

    # Idempotent: a second call does not open a new stream.
    mock_instance.open.reset_mock()
    recorder.start_listening()
    mock_instance.open.assert_not_called()

def test_always_on_start_recording_seeds_from_ring(mock_pyaudio):
    recorder = AudioRecorder(always_listening=True)
    mock_instance = mock_pyaudio.return_value
    mock_stream = MagicMock()
    mock_instance.open.return_value = mock_stream

    recorder.start_listening()
    mock_instance.open.reset_mock()

    # Simulate pre-roll audio captured before the keypress.
    pre_roll = b'\x01\x00' * 512
    recorder._audio_callback(pre_roll, 1024, None, None)

    recorder.start_recording()

    # Frames seeded from the ring buffer; no new stream opened.
    assert recorder.is_recording is True
    assert recorder.frames == [pre_roll]
    mock_instance.open.assert_not_called()

def test_always_on_stop_recording_keeps_stream_open(mock_pyaudio, qtbot):
    recorder = AudioRecorder(always_listening=True)
    mock_instance = mock_pyaudio.return_value
    mock_stream = MagicMock()
    mock_instance.open.return_value = mock_stream

    recorder.start_listening()
    recorder.start_recording()
    recorder.frames = [b'\x00\x00']

    with patch("src.audio_recorder.wave.open") as mock_wave:
        mock_wave.return_value = MagicMock()
        with qtbot.waitSignal(recorder.recording_finished):
            recorder.stop_recording()

    assert recorder.is_recording is False
    # Persistent stream MUST stay open for the next recording.
    assert recorder.stream is mock_stream
    mock_stream.close.assert_not_called()

def test_callback_keeps_persistent_stream_alive(mock_pyaudio):
    recorder = AudioRecorder(always_listening=True)
    # Not recording, but persistent: callback must return paContinue.
    ret_data, flag = recorder._audio_callback(b'\x00\x00' * 512, 1024, None, None)
    import pyaudio
    assert flag == pyaudio.paContinue
    # Ring buffer is always fed.
    assert len(recorder._ring) == 1

def test_legacy_callback_completes_when_not_recording(mock_pyaudio):
    recorder = AudioRecorder(always_listening=False)
    ret_data, flag = recorder._audio_callback(b'\x00\x00' * 512, 1024, None, None)
    import pyaudio
    assert flag == pyaudio.paComplete

def test_set_always_listening_toggle(mock_pyaudio):
    recorder = AudioRecorder(always_listening=False)
    mock_instance = mock_pyaudio.return_value
    mock_stream = MagicMock()
    mock_instance.open.return_value = mock_stream

    # Toggle ON -> opens the persistent stream.
    recorder.set_always_listening(True)
    assert recorder.stream is mock_stream

    # Toggle OFF -> closes the persistent stream while idle.
    recorder.set_always_listening(False)
    assert recorder.stream is None
    mock_stream.close.assert_called_once()

def test_refresh_devices_reinits_portaudio(mock_pyaudio):
    recorder = AudioRecorder(always_listening=True)
    first_instance = mock_pyaudio.return_value
    mock_stream = MagicMock()
    first_instance.open.return_value = mock_stream
    first_instance.get_host_api_count.return_value = 1
    first_instance.get_host_api_info_by_index.return_value = {
        'deviceCount': 1, 'name': 'Windows WASAPI'
    }
    first_instance.get_device_info_by_host_api_device_index.return_value = {
        'maxInputChannels': 1, 'name': 'Mic 1', 'index': 0
    }

    recorder.start_listening()

    devices = recorder.refresh_devices()

    # PortAudio was torn down and re-created (terminate called on old instance,
    # PyAudio constructed again -> called twice total: init + refresh).
    first_instance.terminate.assert_called_once()
    assert mock_pyaudio.call_count == 2
    assert devices == [(0, 'Mic 1 (WASAPI)')]

def test_update_device_reopens_when_always_on(mock_pyaudio):
    recorder = AudioRecorder(always_listening=True)
    mock_instance = mock_pyaudio.return_value
    mock_stream = MagicMock()
    mock_instance.open.return_value = mock_stream

    recorder.start_listening()
    mock_instance.open.reset_mock()

    recorder.update_device(9)

    assert recorder.input_device_index == 9
    # Stream reopened on the new device.
    mock_instance.open.assert_called_once()
    _, kwargs = mock_instance.open.call_args
    assert kwargs.get('input_device_index') == 9

def test_audio_callback_visualizer(mock_pyaudio, qtbot):
    recorder = AudioRecorder(always_listening=False)
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
