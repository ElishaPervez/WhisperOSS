import sounddevice as sd
import wave
import io
import numpy as np
import logging
from PyQt6.QtCore import QObject, pyqtSignal

# Configure logger
logger = logging.getLogger(__name__)

class AudioRecorder(QObject):
    # Signal to send audio amplitude data for visualization (0.0 to 1.0)
    visualizer_update = pyqtSignal(float)
    recording_finished = pyqtSignal(object)  # Emits BytesIO buffer
    error_occurred = pyqtSignal(str)

    def __init__(self, input_device_index=None):
        super().__init__()
        self.input_device_index = input_device_index
        self.is_recording = False
        self.frames = []
        self.stream = None

        # Audio Config
        self.CHANNELS = 1
        self.RATE = 16000  # Whisper expects 16kHz
        self.CHUNK = 1024
        self.DTYPE = np.int16

    def update_device(self, device_index):
        self.input_device_index = device_index

    def start_recording(self):
        if self.is_recording:
            return
        
        try:
            self.frames = []
            self.stream = sd.InputStream(
                samplerate=self.RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                blocksize=self.CHUNK,
                device=self.input_device_index,
                callback=self._audio_callback
            )
            self.is_recording = True
            self.stream.start()
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.error_occurred.emit(f"Failed to start recording: {e}")

    def stop_recording(self):
        if not self.is_recording:
            return

        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error closing stream: {e}")
            finally:
                self.stream = None
        
        # Process audio to in-memory buffer (zero disk I/O)
        self._process_to_memory()

    def _audio_callback(self, indata, frames, time, status):
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        if self.is_recording:
            # indata is already a numpy array, convert to bytes
            self.frames.append(indata.copy().tobytes())
            
            # Calculate amplitude for visualizer using peak
            audio_data = indata.flatten()
            
            # Prevent division by zero or empty errors
            if len(audio_data) == 0:
                self.visualizer_update.emit(0.0)
                return

            # Peak Amplitude Calculation
            peak = np.max(np.abs(audio_data))
            
            # Normalize (adjust divisor based on dtype max value)
            normalized_peak = min(peak / 7000.0, 1.0)
            
            self.visualizer_update.emit(normalized_peak)

    def _process_to_memory(self):
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
            wf.setsampwidth(2)  # 2 bytes for int16
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

    def list_devices(self):
        """Lists available input devices."""
        try:
            devices = []
            device_list = sd.query_devices()
            for i, device in enumerate(device_list):
                if device['max_input_channels'] > 0:
                    devices.append((i, device['name']))
            return devices
        except Exception as e:
            logger.error(f"Error listing devices: {e}")
            return []

    def __del__(self):
        # sounddevice handles cleanup automatically
        pass