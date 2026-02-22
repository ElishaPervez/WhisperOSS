import unittest
import io
import sys
import logging
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread

# Ensure QApplication exists (required for QThread/QObject)
if not QApplication.instance():
    app = QApplication(sys.argv)

from src.services.groq_service import TranscriptionWorker, SearchWorker
from src.groq_client import GroqClient

# Configure logging to suppress errors during tests
logging.basicConfig(level=logging.CRITICAL)

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_groq = MagicMock(spec=GroqClient)
        # Create a mock audio buffer
        self.mock_audio = io.BytesIO(b"fake audio data")

    def test_transcription_pipeline(self):
        """Smoke test for TranscriptionWorker pipeline."""
        print("\nRunning Transcription Pipeline Smoke Test...")

        # Setup mocks
        self.mock_groq.transcribe.return_value = "Hello World"
        self.mock_groq.format_text.return_value = "Hello World Formatted"

        # Create worker
        worker = TranscriptionWorker(
            groq_client=self.mock_groq,
            audio_file=self.mock_audio,
            use_formatter=True,
            format_model="test-model",
            use_translation=False
        )

        # Track signals
        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        # Run synchronous for testing (QThread usually runs in background, but we call run() directly)
        worker.run()

        # Verify interactions
        self.mock_groq.transcribe.assert_called_once()
        self.mock_groq.format_text.assert_called_once()

        # Verify signal emission
        result_signal.assert_called_once_with("Hello World", "Hello World Formatted")
        error_signal.assert_not_called()
        print("Transcription Pipeline: PASS")

    def test_search_pipeline(self):
        """Smoke test for SearchWorker pipeline."""
        print("\nRunning Search Pipeline Smoke Test...")

        # Setup mocks
        self.mock_groq.transcribe.return_value = "What is the capital of France?"
        self.mock_groq.format_text.return_value = "What is the capital of France?" # Refined
        self.mock_groq.run_search.return_value = "Paris"

        # Create worker
        worker = SearchWorker(
            groq_client=self.mock_groq,
            audio_file=self.mock_audio
        )

        # Track signals
        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        # Run synchronous for testing
        worker.run()

        # Verify interactions
        self.mock_groq.transcribe.assert_called_once()
        self.mock_groq.format_text.assert_called_once() # Refinement step
        self.mock_groq.run_search.assert_called_once()

        # Verify signal emission
        result_signal.assert_called_once_with("Paris")
        error_signal.assert_not_called()
        print("Search Pipeline: PASS")

    def test_search_pipeline_proxy_fallback_to_groq(self):
        """Proxy search errors should automatically fall back to Groq search."""
        print("\nRunning Search Pipeline Proxy Fallback Smoke Test...")

        self.mock_groq.transcribe.return_value = "What is the weather in Karachi?"
        self.mock_groq.format_text.return_value = "weather in karachi now"
        self.mock_groq.run_search.return_value = "Karachi: 25°C, 57% humidity"

        mock_proxy = MagicMock()
        mock_proxy.run_search.side_effect = RuntimeError("proxy offline")

        worker = SearchWorker(
            groq_client=self.mock_groq,
            audio_file=self.mock_audio,
            search_client=mock_proxy,
        )

        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        worker.run()

        mock_proxy.run_search.assert_called_once_with("weather in karachi now")
        self.mock_groq.run_search.assert_called_once_with("weather in karachi now")
        result_signal.assert_called_once_with("Karachi: 25°C, 57% humidity")
        error_signal.assert_not_called()
        print("Search Pipeline Proxy Fallback: PASS")

if __name__ == "__main__":
    unittest.main()
