import pyaudio
import wave
import os
import tempfile
import threading
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

class AudioRecorder(QObject):
    # Signal to send audio amplitude data for visualization (0.0 to 1.0)
    visualizer_update = pyqtSignal(float)
    recording_finished = pyqtSignal(str) # Emits path to saved file
    error_occurred = pyqtSignal(str)

    def __init__(self, input_device_index=None):
        super().__init__()
        self.input_device_index = input_device_index
        self.is_recording = False
        self.frames = []
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.filename = os.path.join(tempfile.gettempdir(), "whisper_oss_recording.wav")

        # Audio Config
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000 # Whisper expects 16kHz
        self.CHUNK = 1024

    def update_device(self, device_index):
        self.input_device_index = device_index

    def start_recording(self):
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
            self.error_occurred.emit(f"Failed to start recording: {e}")

    def stop_recording(self):
        if not self.is_recording:
            return

        self.is_recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        self._save_file()
        self.recording_finished.emit(self.filename)

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if self.is_recording:
            self.frames.append(in_data)
            # Calculate amplitude for visualizer using RMS (Root Mean Square)
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            
            # Prevent division by zero or empty errors
            if len(audio_data) == 0:
                self.visualizer_update.emit(0.0)
                return (in_data, pyaudio.paContinue)

            # RMS Calculation
            rms = np.sqrt(np.mean(audio_data.astype(np.float64)**2))
            
            # Normalize: RMS of sine wave at max volume (32767) is ~23169
            # Typical speech might be 500-5000 range.
            # We want good visual movement for normal speech.
            # Let's saturate at 10000 RMS.
            normalized_peak = min(rms / 5000.0, 1.0)
            
            self.visualizer_update.emit(normalized_peak)
            return (in_data, pyaudio.paContinue)
        return (None, pyaudio.paComplete)

    def _save_file(self):
        try:
            wf = wave.open(self.filename, 'wb')
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.p.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()
        except Exception as e:
            self.error_occurred.emit(f"Failed to save file: {e}")

    def list_devices(self):
        info = self.p.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        devices = []
        for i in range(num_devices):
            if (self.p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                devices.append((i, self.p.get_device_info_by_host_api_device_index(0, i).get('name')))
        return devices

    def __del__(self):
        self.p.terminate()
