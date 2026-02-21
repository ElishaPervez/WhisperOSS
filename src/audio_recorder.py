import pyaudio
import wave
import io
import threading
import numpy as np
import logging
from typing import Optional, List, Tuple, Any, Union
from PyQt6.QtCore import QObject, pyqtSignal

# Configure logger
logger = logging.getLogger(__name__)

class AudioRecorder(QObject):
    # Signal to send audio amplitude data for visualization (0.0 to 1.0)
    visualizer_update = pyqtSignal(float)
    recording_finished = pyqtSignal(object)  # Emits BytesIO buffer (changed from str)
    error_occurred = pyqtSignal(str)

    def __init__(self, input_device_index: Optional[int] = None):
        super().__init__()
        self.input_device_index = input_device_index
        self.is_recording = False
        self.frames: List[bytes] = []
        self.p = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None

        # Audio Config
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000 # Whisper expects 16kHz
        self.CHUNK = 1024

        # Decimation counter for visualizer updates to reduce UI thread load
        self._viz_counter = 0

    def update_device(self, device_index: int) -> None:
        self.input_device_index = device_index

    def start_recording(self) -> None:
        if self.is_recording:
            return

        try:
            self.frames = []
            self.stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.CHUNK,
                stream_callback=self._audio_callback
            )
            self.is_recording = True
            self.stream.start_stream()
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.error_occurred.emit(f"Failed to start recording: {e}")

    def stop_recording(self) -> None:
        if not self.is_recording:
            return

        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error closing stream: {e}")
            finally:
                self.stream = None

        # Process audio to in-memory buffer (zero disk I/O)
        self._process_to_memory()

    def _audio_callback(self, in_data: bytes, frame_count: int, time_info: dict, status: int) -> Tuple[Optional[bytes], int]:
        if self.is_recording:
            self.frames.append(in_data)
            # Calculate amplitude for visualizer using RMS (Root Mean Square)
            audio_data = np.frombuffer(in_data, dtype=np.int16)

            # Prevent division by zero or empty errors
            if len(audio_data) == 0:
                self.visualizer_update.emit(0.0)
                return (in_data, pyaudio.paContinue)

            # Peak Amplitude Calculation (Optimized)
            peak = np.max(np.abs(audio_data))

            # Normalize
            normalized_peak = min(peak / 7000.0, 1.0)

            # Decimate visualizer updates: emit only every 3rd frame
            self._viz_counter += 1
            if self._viz_counter % 3 == 0:
                self.visualizer_update.emit(normalized_peak)
                self._viz_counter = 0

            return (in_data, pyaudio.paContinue)
        return (None, pyaudio.paComplete)

    def _process_to_memory(self) -> None:
        """Process recorded audio to in-memory BytesIO buffer (zero disk latency)."""
        try:
            if not self.frames:
                logger.warning("No audio frames to process")
                self.error_occurred.emit("No audio recorded")
                return

            # Create in-memory WAV file
            wav_buffer = io.BytesIO()
            wf = wave.open(wav_buffer, 'wb')
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.p.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()

            # Reset cursor to start for reading
            wav_buffer.seek(0)

            logger.info(f"Audio processed to memory buffer: {wav_buffer.getbuffer().nbytes} bytes")
            self.recording_finished.emit(wav_buffer)

        except Exception as e:
            logger.error(f"Failed to process audio to memory: {e}")
            self.error_occurred.emit(f"Failed to process audio: {e}")

    def list_devices(self) -> List[Tuple[int, str]]:
        """Lists available input devices."""
        try:
            info = self.p.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount')
            devices = []
            if num_devices:
                for i in range(num_devices):
                    device_info = self.p.get_device_info_by_host_api_device_index(0, i)
                    if device_info.get('maxInputChannels') > 0:
                        name = device_info.get('name')
                        if name:
                            devices.append((i, name))
            return devices
        except Exception as e:
            logger.error(f"Error listing devices: {e}")
            return []

    def __del__(self) -> None:
        try:
            self.p.terminate()
        except Exception:
            pass
