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
        self.mock_gemini = MagicMock()
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
        self.mock_gemini.run_search.return_value = "Paris"

        # Create worker
        worker = SearchWorker(
            groq_client=self.mock_groq,
            gemini_client=self.mock_gemini,
            gemini_model_id="models/gemma-4-31b-it",
            audio_file=self.mock_audio,
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
        self.mock_gemini.run_search.assert_called_once_with(
            "What is the capital of France?",
            model_id="models/gemma-4-31b-it",
            system_prompt=worker._system_prompt_for_request(),
            image_bytes=None,
            stream_callback=worker._emit_stream_text,
            thought_callback=worker._emit_thought_text,
            with_search=True,
        )

        # Verify signal emission
        result_signal.assert_called_once_with("Paris")
        error_signal.assert_not_called()
        print("Search Pipeline: PASS")

    def test_search_pipeline_with_selected_text_context(self):
        """Selected text should be sent as explicit context to Gemini."""
        print("\nRunning Search Pipeline Selected Context Smoke Test...")

        self.mock_groq.transcribe.return_value = "What does this mean?"
        self.mock_gemini.run_search.return_value = "Quixotic means extremely idealistic."

        worker = SearchWorker(
            groq_client=self.mock_groq,
            audio_file=self.mock_audio,
            gemini_client=self.mock_gemini,
            gemini_model_id="models/gemma-4-31b-it",
            selected_text="quixotic",
        )

        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        worker.run()

        self.mock_gemini.run_search.assert_called_once_with(
            "Query: What does this mean?\nSelected: quixotic",
            model_id="models/gemma-4-31b-it",
            system_prompt=worker._system_prompt_for_request(),
            image_bytes=None,
            stream_callback=worker._emit_stream_text,
            thought_callback=worker._emit_thought_text,
            with_search=True,
        )
        result_signal.assert_called_once_with("Quixotic means extremely idealistic.")
        error_signal.assert_not_called()
        print("Search Pipeline Selected Context: PASS")

    def test_gemini_search_exception_emits_error_not_answer(self):
        """Gemini errors must propagate to the error signal."""
        print("\nRunning Gemini Search Exception → Error Signal Test...")

        self.mock_gemini.run_search.side_effect = RuntimeError("network down")

        worker = SearchWorker(
            groq_client=self.mock_groq,
            gemini_client=self.mock_gemini,
            gemini_model_id="models/gemma-4-31b-it",
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
        print("Gemini Search Exception → Error Signal: PASS")

    def test_search_pipeline_with_image_context_uses_gemini_payload(self):
        """Image context should be forwarded to Gemini when available."""
        print("\nRunning Search Pipeline Image Context Smoke Test...")

        self.mock_groq.transcribe.return_value = "What is this button?"
        self.mock_gemini.run_search.return_value = "This is a submit button."

        worker = SearchWorker(
            groq_client=self.mock_groq,
            gemini_client=self.mock_gemini,
            gemini_model_id="models/gemma-4-31b-it",
            audio_file=self.mock_audio,
            image_png_bytes=b"\x89PNG\r\n\x1a\nfake",
        )

        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        worker.run()

        self.mock_gemini.run_search.assert_called_once()
        _, kwargs = self.mock_gemini.run_search.call_args
        assert kwargs["model_id"] == "models/gemma-4-31b-it"
        assert kwargs["system_prompt"] == worker._system_prompt_for_request()
        assert kwargs["image_bytes"].startswith(b"\x89PNG")
        result_signal.assert_called_once_with("This is a submit button.")
        error_signal.assert_not_called()
        print("Search Pipeline Image Context: PASS")

    def test_search_pipeline_skips_transcribe_when_query_text_is_provided(self):
        """Pre-transcribed query text should bypass Whisper transcription in SearchWorker."""
        print("\nRunning Search Pipeline Pre-Transcribed Query Smoke Test...")

        self.mock_gemini.run_search.return_value = "DNS maps names to IP addresses."

        worker = SearchWorker(
            groq_client=self.mock_groq,
            gemini_client=self.mock_gemini,
            gemini_model_id="models/gemma-4-31b-it",
            audio_file=None,
            query_text="What is DNS?",
        )

        result_signal = MagicMock()
        worker.finished.connect(result_signal)

        error_signal = MagicMock()
        worker.error.connect(error_signal)

        worker.run()

        self.mock_groq.transcribe.assert_not_called()
        self.mock_gemini.run_search.assert_called_once_with(
            "What is DNS?",
            model_id="models/gemma-4-31b-it",
            system_prompt=worker._system_prompt_for_request(),
            image_bytes=None,
            stream_callback=worker._emit_stream_text,
            thought_callback=worker._emit_thought_text,
            with_search=True,
        )
        result_signal.assert_called_once_with("DNS maps names to IP addresses.")
        error_signal.assert_not_called()
        print("Search Pipeline Pre-Transcribed Query: PASS")

    def test_search_pipeline_emits_thought_text(self):
        """Gemini thought chunks should be forwarded separately from answer chunks."""
        self.mock_gemini.run_search.side_effect = lambda *args, **kwargs: (
            kwargs["thought_callback"]("I will search first. ") or "Final answer"
        )

        worker = SearchWorker(
            groq_client=self.mock_groq,
            gemini_client=self.mock_gemini,
            gemini_model_id="models/gemma-4-31b-it",
            audio_file=None,
            query_text="What changed today?",
        )

        thought_signal = MagicMock()
        result_signal = MagicMock()
        worker.thought_text.connect(thought_signal)
        worker.finished.connect(result_signal)

        worker.run()

        thought_signal.assert_called_once_with("I will search first. ")
        result_signal.assert_called_once_with("Final answer")

    def test_formatter_always_uses_default_prompt(self):
        """TranscriptionWorker should always use the default formatter prompt."""
        print("\nRunning Formatter Default Prompt Test...")

        from src.prompts import SYSTEM_PROMPT_DEFAULT

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

        # The system prompt passed to format_text must be the default prompt.
        _, kwargs = self.mock_groq.format_text.call_args
        used_prompt = kwargs.get("system_prompt") or self.mock_groq.format_text.call_args[0][2]
        assert used_prompt.strip() == SYSTEM_PROMPT_DEFAULT.strip(), (
            f"Expected default prompt, got: {used_prompt[:80]!r}"
        )
        print("Formatter Default Prompt: PASS")


if __name__ == "__main__":
    unittest.main()
