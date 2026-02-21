import logging
from typing import Optional, Union, Tuple
import io

from PyQt6.QtCore import QThread, pyqtSignal
from src.groq_client import GroqClient

# Configure logger
logger = logging.getLogger(__name__)

class TranscriptionWorker(QThread):
    finished = pyqtSignal(str, str) # raw_text, final_text
    error = pyqtSignal(str)

    def __init__(self,
                 groq_client: GroqClient,
                 audio_file: Union[str, io.BytesIO],
                 use_formatter: bool,
                 format_model: str,
                 use_translation: bool = False,
                 target_language: str = "English",
                 formatting_style: str = "Default",
                 active_context: str = ""):
        super().__init__()
        self.groq_client = groq_client
        self.audio_file = audio_file
        self.use_formatter = use_formatter
        self.format_model = format_model
        self.use_translation = use_translation
        self.target_language = target_language
        self.formatting_style = formatting_style
        self.active_context = active_context

    def run(self) -> None:
        try:
            # Step 1: Transcribe with prompt for better accuracy
            from src.prompts import TRANSCRIPTION_PROMPT
            raw_text = self.groq_client.transcribe(self.audio_file, prompt=TRANSCRIPTION_PROMPT)
            final_text = raw_text

            # Step 2: Format / Translate (Optional)
            if self.use_formatter:
                if self.use_translation:
                    from src.prompts import SYSTEM_PROMPT_TRANSLATOR
                    prompt = SYSTEM_PROMPT_TRANSLATOR.format(language=self.target_language)
                    logger.info(f"Using Translator Prompt for language: {self.target_language}")
                    formatted = self.groq_client.format_text(raw_text, self.format_model, system_prompt=prompt)
                else:
                    from src.prompts import get_formatter_prompt
                    prompt = get_formatter_prompt(self.formatting_style)
                    # Inject context intelligence if available
                    if self.active_context:
                        prompt += f"\n\nContext: The user is currently typing in '{self.active_context}'. Adjust formatting accordingly."
                    logger.info(f"Using Formatter Prompt for style: {self.formatting_style}, context: {self.active_context or 'None'}")
                    formatted = self.groq_client.format_text(raw_text, self.format_model, system_prompt=prompt)

                final_text = formatted

            self.finished.emit(raw_text, final_text)

        except Exception as e:
            logger.error(f"TranscriptionWorker error: {e}")
            self.error.emit(str(e))

class SearchWorker(QThread):
    finished = pyqtSignal(str) # final_answer
    error = pyqtSignal(str)

    def __init__(self,
                 groq_client: GroqClient,
                 audio_file: Union[str, io.BytesIO],
                 refinement_model_id: str = "openai/gpt-oss-120b"):
        super().__init__()
        self.groq_client = groq_client
        self.audio_file = audio_file
        self.refinement_model_id = refinement_model_id

    def run(self) -> None:
        try:
            # Step 1: Transcribe using standard Whisper model
            # We use the standard prompt for accuracy
            from src.prompts import TRANSCRIPTION_PROMPT, SYSTEM_PROMPT_REFINE
            query_text = self.groq_client.transcribe(self.audio_file, prompt=TRANSCRIPTION_PROMPT)

            if not query_text or not query_text.strip():
                self.error.emit("No speech detected.")
                return

            # Step 2: Refine Query
            # Using the high-intelligence model (e.g. Llama 3 70B) to clean up the query
            refined_query = self.groq_client.format_text(
                query_text,
                model_id=self.refinement_model_id,
                system_prompt=SYSTEM_PROMPT_REFINE
            )

            logger.info(f"Refined query ({self.refinement_model_id}): '{query_text}' -> '{refined_query}'")

            # Step 3: Search / Answer using Compound model
            answer = self.groq_client.run_search(refined_query)
            self.finished.emit(answer)

        except Exception as e:
            logger.error(f"SearchWorker error: {e}")
            self.error.emit(str(e))
