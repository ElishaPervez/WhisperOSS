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

    def test_search_pipeline_proxy_fallback_to_groq_text_only(self):
        """Text-only proxy failure should fall back to Groq search (no image context)."""
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
        print("Search Pipeline Proxy Fallback (text): PASS")

    def test_image_search_proxy_failure_emits_error_not_silent_fallback(self):
        """When proxy fails and image context is present the worker must emit an error,
        never silently fall back to text-only Groq search."""
        print("\nRunning Image Search Proxy Failure → Explicit Error Test...")

        self.mock_groq.format_text.return_value = "identify this UI button"

        mock_proxy = MagicMock()
        mock_proxy.run_search.side_effect = RuntimeError("proxy offline")

        worker = SearchWorker(
            groq_client=self.mock_groq,
            audio_file=None,
            query_text="What is this button?",
            search_client=mock_proxy,
            image_png_bytes=b"\x89PNG\r\n\x1a\nfake",
        )

        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        worker.run()

        # Must surface an error, not a silent text-only fallback answer.
        error_signal.assert_called_once()
        error_msg = error_signal.call_args[0][0]
        assert "image" in error_msg.lower() or "proxy" in error_msg.lower(), (
            f"Error message should mention image or proxy, got: {error_msg!r}"
        )
        result_signal.assert_not_called()
        # Groq fallback must NOT be called when image context is present.
        self.mock_groq.run_search.assert_not_called()
        print("Image Search Proxy Failure → Explicit Error: PASS")

    def test_groq_search_exception_emits_error_not_answer(self):
        """GroqClient.run_search() raising must propagate to the error signal,
        not appear as a successful answer string."""
        print("\nRunning Groq Search Exception → Error Signal Test...")

        from src.groq_client import GroqClientError

        self.mock_groq.format_text.return_value = "capital of France"
        self.mock_groq.run_search.side_effect = GroqClientError("Search failed: network down")

        worker = SearchWorker(
            groq_client=self.mock_groq,
            audio_file=None,
            query_text="What is the capital of France?",
        )

        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        worker.run()

        error_signal.assert_called_once()
        result_signal.assert_not_called()
        print("Groq Search Exception → Error Signal: PASS")

    def test_search_pipeline_with_selected_text_context(self):
        """Selected text should be sent as explicit context to the refinement step."""
        print("\nRunning Search Pipeline Selected Context Smoke Test...")

        self.mock_groq.transcribe.return_value = "What does this mean?"
        self.mock_groq.format_text.return_value = "meaning of quixotic"
        self.mock_groq.run_search.return_value = "Quixotic means extremely idealistic."

        worker = SearchWorker(
            groq_client=self.mock_groq,
            audio_file=self.mock_audio,
            selected_text="quixotic",
        )

        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        worker.run()

        self.mock_groq.transcribe.assert_called_once()
        self.mock_groq.format_text.assert_called_once()
        refine_input = self.mock_groq.format_text.call_args[0][0]
        assert "Spoken: What does this mean?" in refine_input
        assert "Selected: quixotic" in refine_input
        self.mock_groq.run_search.assert_called_once_with(
            "Query: meaning of quixotic\nSelected: quixotic"
        )
        result_signal.assert_called_once_with("Quixotic means extremely idealistic.")
        error_signal.assert_not_called()
        print("Search Pipeline Selected Context: PASS")

    def test_search_pipeline_with_image_context_uses_proxy_payload(self):
        """Image context should be forwarded to proxy search when available."""
        print("\nRunning Search Pipeline Image Context Smoke Test...")

        self.mock_groq.transcribe.return_value = "What is this button?"
        self.mock_groq.format_text.return_value = "identify this UI button"
        self.mock_groq.run_search.return_value = "fallback not used"

        mock_proxy = MagicMock()
        mock_proxy.run_search.return_value = "This is a submit button."

        worker = SearchWorker(
            groq_client=self.mock_groq,
            audio_file=self.mock_audio,
            search_client=mock_proxy,
            image_png_bytes=b"\x89PNG\r\n\x1a\nfake",
        )

        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        worker.run()

        mock_proxy.run_search.assert_called_once()
        _, kwargs = mock_proxy.run_search.call_args
        assert kwargs["image_bytes"].startswith(b"\x89PNG")
        result_signal.assert_called_once_with("This is a submit button.")
        error_signal.assert_not_called()
        print("Search Pipeline Image Context: PASS")

    def test_search_pipeline_skips_transcribe_when_query_text_is_provided(self):
        """Pre-transcribed query text should bypass Whisper transcription in SearchWorker."""
        print("\nRunning Search Pipeline Pre-Transcribed Query Smoke Test...")

        self.mock_groq.format_text.return_value = "what is dns"
        self.mock_groq.run_search.return_value = "DNS maps names to IP addresses."

        worker = SearchWorker(
            groq_client=self.mock_groq,
            audio_file=None,
            query_text="What is DNS?",
        )

        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        worker.run()

        self.mock_groq.transcribe.assert_not_called()
        self.mock_groq.format_text.assert_called_once()
        self.mock_groq.run_search.assert_called_once_with("what is dns")
        result_signal.assert_called_once_with("DNS maps names to IP addresses.")
        error_signal.assert_not_called()
        print("Search Pipeline Pre-Transcribed Query: PASS")

    def test_formatting_style_flows_from_worker_to_prompt(self):
        """TranscriptionWorker must pass formatting_style to get_formatter_prompt."""
        print("\nRunning Formatting Style → Prompt Flow Test...")

        from src.prompts import SYSTEM_PROMPT_EMAIL

        self.mock_groq.transcribe.return_value = "please send the report by friday"
        self.mock_groq.format_text.return_value = "Please send the report by Friday."

        worker = TranscriptionWorker(
            groq_client=self.mock_groq,
            audio_file=self.mock_audio,
            use_formatter=True,
            format_model="test-model",
            formatting_style="Email",
        )

        finished_signal = MagicMock()
        worker.finished.connect(finished_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        worker.run()

        error_signal.assert_not_called()
        finished_signal.assert_called_once()

        # The system prompt passed to format_text must be the Email prompt.
        _, kwargs = self.mock_groq.format_text.call_args
        used_prompt = kwargs.get("system_prompt") or self.mock_groq.format_text.call_args[0][2]
        assert "email" in used_prompt.lower() or "professional" in used_prompt.lower(), (
            f"Expected Email prompt, got: {used_prompt[:80]!r}"
        )
        print("Formatting Style → Prompt Flow: PASS")


if __name__ == "__main__":
    unittest.main()
