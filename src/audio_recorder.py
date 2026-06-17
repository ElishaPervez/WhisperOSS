import pyaudio
import wave
import io
import threading
import collections
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

    def __init__(self, input_device_index: Optional[int] = None, always_listening: bool = True):
        super().__init__()
        self.input_device_index = input_device_index
        self.always_listening = always_listening
        self.is_recording = False
        self.frames: List[bytes] = []
        self.p = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None

        # Audio Config
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000 # Nominal/fallback rate; actual capture rate is resolved
                          # per device (WASAPI only accepts the device's native rate).
        self.CHUNK = 1024

        # The sample rate we actually open the stream at. Resolved from the
        # selected device each time a stream opens; the WAV is written at this
        # rate and the Groq Whisper endpoint resamples server-side.
        self._capture_rate = self.RATE

        # Pre-roll ring buffer (~0.5s of audio). Always fed by the persistent
        # stream so the moment recording starts we can seed self.frames with the
        # audio captured just BEFORE the keypress (eliminates first-word clipping).
        self._PREROLL_SECONDS = 0.5
        ring_len = max(1, int((self.RATE * self._PREROLL_SECONDS) / self.CHUNK))
        self._ring: "collections.deque[bytes]" = collections.deque(maxlen=ring_len)

        # Guards the seed of self.frames + the is_recording flip and the
        # callback's append to self.frames so they never race.
        self._lock = threading.Lock()

        # Decimation counter for visualizer updates to reduce UI thread load
        self._viz_counter = 0
        self._viz_emit_every = 1

    def start_listening(self) -> None:
        """Open the persistent pre-roll stream if always_listening. Idempotent."""
        if not self.always_listening:
            return
        if self.stream is not None:
            return
        self._open_persistent_stream()

    def stop_listening(self) -> None:
        """Close the persistent stream (shutdown / toggle-off). No-op while recording."""
        if self.is_recording:
            return
        self._close_stream()

    def set_always_listening(self, enabled: bool) -> None:
        """Toggle handler: open or close the persistent stream."""
        self.always_listening = enabled
        if enabled:
            self.start_listening()
        else:
            # Only tear down the persistent stream when idle; if a recording is
            # in progress the legacy close happens at stop_recording().
            if not self.is_recording:
                self._close_stream()

    def _open_persistent_stream(self) -> None:
        """Open a continuously-running input stream that feeds the ring buffer."""
        try:
            self._prepare_capture_rate()
            self._ring.clear()
            self.stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self._capture_rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.CHUNK,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
        except Exception as e:
            self.stream = None
            logger.error(f"Failed to open persistent stream: {e}")
            self.error_occurred.emit(f"Failed to open microphone: {e}")

    def _close_stream(self) -> None:
        """Stop and close the active stream (persistent or legacy)."""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error closing stream: {e}")
            finally:
                self.stream = None

    def _resolve_capture_rate(self) -> int:
        """Return a sample rate the selected device actually supports.

        WASAPI (the preferred host API) only accepts the device's native mixer
        rate in shared mode, so opening at a hardcoded 16 kHz fails with
        paInvalidSampleRate (-9997). We capture at the device's default rate
        instead and let the Groq Whisper endpoint resample the uploaded WAV.
        """
        try:
            if self.input_device_index is not None:
                info = self.p.get_device_info_by_index(self.input_device_index)
            else:
                info = self.p.get_default_input_device_info()
            rate_val = info.get('defaultSampleRate')
            if isinstance(rate_val, (int, float)) and rate_val > 0:
                return int(round(rate_val))
        except Exception as e:
            logger.warning(f"Could not resolve device sample rate; using {self.RATE} Hz: {e}")
        return self.RATE

    def _prepare_capture_rate(self) -> None:
        """Resolve the capture rate for the current device and size the pre-roll
        ring (~_PREROLL_SECONDS) for that rate so pre-roll duration is correct."""
        self._capture_rate = self._resolve_capture_rate()
        ring_len = max(1, int((self._capture_rate * self._PREROLL_SECONDS) / self.CHUNK))
        if self._ring.maxlen != ring_len:
            # Re-create with the correct capacity (ring is cleared right after).
            self._ring = collections.deque(self._ring, maxlen=ring_len)

    def update_device(self, device_index: int) -> None:
        self.input_device_index = device_index
        # In always-on mode, hop the persistent stream to the newly selected
        # device immediately (only when idle so we never disturb a recording).
        if self.always_listening and not self.is_recording:
            self._close_stream()
            self.start_listening()

    def start_recording(self) -> None:
        if self.is_recording:
            return

        if self.always_listening:
            # Persistent stream is already running and feeding the ring buffer.
            # Make sure it is actually open (e.g. first launch or after refresh).
            if self.stream is None:
                self._open_persistent_stream()
                if self.stream is None:
                    return
            # Seed frames from the pre-roll ring and flip the flag atomically so
            # the callback starts appending immediately after the seeded audio.
            with self._lock:
                self.frames = list(self._ring)
                self.is_recording = True
            return

        # Legacy path: open a fresh stream on demand.
        try:
            self.frames = []
            self._prepare_capture_rate()
            self.stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self._capture_rate,
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

        with self._lock:
            self.is_recording = False

        if not self.always_listening:
            # Legacy path: close the on-demand stream.
            self._close_stream()
        # Always-on path: KEEP the persistent stream open so the ring buffer
        # keeps filling for the next recording (no re-open latency / clipping).

        # Process audio to in-memory buffer (zero disk I/O)
        self._process_to_memory()

    def _audio_callback(self, in_data: bytes, frame_count: int, time_info: dict, status: int) -> Tuple[Optional[bytes], int]:
        # Always feed the pre-roll ring (cheap) so we have audio from just before
        # the user pressed record.
        self._ring.append(in_data)

        if self.is_recording:
            with self._lock:
                # Re-check under the lock: stop_recording() may have flipped the
                # flag between the check above and acquiring the lock.
                if self.is_recording:
                    self.frames.append(in_data)
            # Calculate amplitude for visualizer
            audio_data = np.frombuffer(in_data, dtype=np.int16)

            # Prevent division by zero or empty errors
            if len(audio_data) == 0:
                self.visualizer_update.emit(0.0)
                return (in_data, pyaudio.paContinue)

            # Peak Amplitude Calculation (Optimized)
            peak = np.max(np.abs(audio_data))

            normalized_peak = self._normalize_peak_for_visualizer(int(peak))

            # Emit at a controlled cadence to keep UI responsive without flooding.
            self._viz_counter += 1
            if self._viz_counter % self._viz_emit_every == 0:
                self.visualizer_update.emit(normalized_peak)
                self._viz_counter = 0

            return (in_data, pyaudio.paContinue)

        # Persistent (always-on) stream must keep running even when not recording.
        if self.always_listening:
            return (in_data, pyaudio.paContinue)

        # Legacy stream is single-shot: signal completion so it can be closed.
        return (None, pyaudio.paComplete)

    def _normalize_peak_for_visualizer(self, peak: int) -> float:
        """
        Map raw int16 peak amplitude into a visualizer-friendly 0..1 range.
        A light non-linear curve makes low-volume speech more reactive.
        """
        linear = min(max(float(peak) / 7000.0, 0.0), 1.0)
        return min((linear ** 0.72) * 1.18, 1.0)

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
            # Write at the rate we actually captured (matches the device's native
            # rate so the WAV plays back at correct pitch; Groq resamples to 16kHz).
            wf.setframerate(self._capture_rate)
            wf.writeframes(b''.join(self.frames))
            wf.close()

            # Reset cursor to start for reading
            wav_buffer.seek(0)

            logger.info(f"Audio processed to memory buffer: {wav_buffer.getbuffer().nbytes} bytes")
            self.recording_finished.emit(wav_buffer)

        except Exception as e:
            logger.error(f"Failed to process audio to memory: {e}")
            self.error_occurred.emit(f"Failed to process audio: {e}")

    # Host API preference + display labels (Windows). WASAPI is the modern,
    # low-latency API and exposes virtual devices like NVIDIA Broadcast; we list
    # it first and collapse the same physical mic that Windows ALSO exposes
    # through the older MME / DirectSound / WDM-KS subsystems into one entry.
    _HOST_API_PRIORITY = [
        ("wasapi", "WASAPI"),
        ("wdm-ks", "WDM-KS"),
        ("directsound", "DirectSound"),
        ("mme", "MME"),
    ]

    @classmethod
    def _host_api_label_and_rank(cls, host_api_name: Optional[str]) -> Tuple[str, int]:
        """Map a PortAudio host API name to a short label and a preference rank."""
        name = (host_api_name or "").lower()
        for rank, (needle, label) in enumerate(cls._HOST_API_PRIORITY):
            if needle in name:
                return label, rank
        # Unknown/other host APIs sort after the known ones but are still shown.
        return (host_api_name or "Audio"), len(cls._HOST_API_PRIORITY)

    @staticmethod
    def _normalize_device_name(name: Optional[str]) -> str:
        return "".join(ch for ch in (name or "").lower() if ch.isalnum())

    @staticmethod
    def _is_same_device(key: str, seen_key: str) -> bool:
        """True if two normalized device names refer to the same physical mic.

        Exact match, or one name is a prefix of the other for reasonably long
        names — this collapses MME's truncated (~31 char) name onto the full
        WASAPI name without merging genuinely distinct devices.
        """
        if not key or not seen_key:
            return False
        if key == seen_key:
            return True
        if min(len(key), len(seen_key)) >= 12 and (
            key.startswith(seen_key) or seen_key.startswith(key)
        ):
            return True
        return False

    def list_devices(self) -> List[Tuple[int, str]]:
        """List input devices, one clean entry per physical microphone.

        Enumerates ALL host APIs (so virtual/late devices like NVIDIA Broadcast
        appear), then collapses the same mic that Windows exposes through several
        audio subsystems into a single entry, preferring WASAPI. The GLOBAL
        device index (device_info["index"]) is the stored id, and every
        per-device query is wrapped in try/except so one bad/warming-up device
        cannot blank the entire list.
        """
        try:
            host_api_count = self.p.get_host_api_count()
        except Exception as e:
            logger.error(f"Error querying host APIs: {e}")
            return []

        # 1) Gather every input device with its host API label + preference rank.
        candidates: List[Tuple[int, int, str, str]] = []  # (rank, index, name, label)
        for host_api_index in range(host_api_count):
            try:
                host_info = self.p.get_host_api_info_by_index(host_api_index)
                num_devices = host_info.get('deviceCount') or 0
                label, rank = self._host_api_label_and_rank(host_info.get('name'))
            except Exception as e:
                logger.warning(f"Skipping host API {host_api_index}: {e}")
                continue

            for i in range(num_devices):
                try:
                    device_info = self.p.get_device_info_by_host_api_device_index(host_api_index, i)
                    if (device_info.get('maxInputChannels') or 0) <= 0:
                        continue
                    global_index = device_info.get('index')
                    name = device_info.get('name')
                    if global_index is None or not name:
                        continue
                    candidates.append((rank, int(global_index), name, label))
                except Exception as e:
                    # One bad/warming-up device must not drop the whole list.
                    logger.warning(f"Skipping device {i} on host API {host_api_index}: {e}")
                    continue

        # 2) In host-API preference order, keep one entry per physical device.
        candidates.sort(key=lambda c: (c[0], c[1]))
        devices: List[Tuple[int, str]] = []
        seen_indices: set = set()
        seen_keys: List[str] = []
        for _rank, global_index, name, label in candidates:
            if global_index in seen_indices:
                continue
            key = self._normalize_device_name(name)
            if any(self._is_same_device(key, s) for s in seen_keys):
                continue
            seen_indices.add(global_index)
            seen_keys.append(key)
            devices.append((global_index, f"{name} ({label})"))

        return devices

    def refresh_devices(self) -> List[Tuple[int, str]]:
        """Re-init PortAudio so hot-plugged mics appear, then enumerate.

        A fresh PyAudio instance is what surfaces devices connected after launch.
        Only re-inits when idle; reopens the persistent stream if it was open.
        """
        if not self.is_recording:
            was_listening = self.stream is not None
            # Tear down the persistent stream before re-initializing PortAudio.
            self._close_stream()
            try:
                self.p.terminate()
            except Exception as e:
                logger.error(f"Error terminating PortAudio: {e}")
            self.p = pyaudio.PyAudio()
            # Reopen the persistent stream on the fresh PortAudio instance.
            if was_listening or self.always_listening:
                self.start_listening()

        return self.list_devices()

    def __del__(self) -> None:
        try:
            self.p.terminate()
        except Exception:
            pass
