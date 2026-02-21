import os
import logging
from typing import List, Tuple, Optional, Union, Any
from groq import Groq, APIConnectionError, APIStatusError
from src.prompts import SYSTEM_PROMPT_FORMATTER

# Configure logger
logger = logging.getLogger(__name__)

class GroqClientError(Exception):
    """Custom exception for Groq Client errors."""
    pass

class GroqClient:
    def __init__(self, api_key: Optional[str]):
        self.client: Optional[Groq] = None
        if api_key:
            self.update_api_key(api_key)

    def update_api_key(self, api_key: str) -> None:
        try:
            clean_key = api_key.strip() if api_key else ""
            self.client = Groq(api_key=clean_key)
        except Exception as e:
            logger.error(f"Error initializing Groq client: {e}")
            self.client = None

    def check_connection(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.models.list()
            return True
        except Exception:
            return False

    def list_models(self) -> Tuple[List[str], List[str]]:
        if not self.client:
            return [], []

        try:
            models = self.client.models.list()
            all_models = models.data

            transcription_models = [m.id for m in all_models if 'whisper' in m.id]
            llm_models = [m.id for m in all_models if 'whisper' not in m.id]

            return transcription_models, llm_models
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return [], []

    def transcribe(self, file_source: Union[str, Any], model_id: str = "whisper-large-v3", prompt: Optional[str] = None) -> str:
        """
        Transcribe audio using Whisper model.

        Args:
            file_source: Path to audio file OR BytesIO buffer (for zero-latency)
            model_id: Whisper model to use
            prompt: Optional prompt to guide transcription accuracy.
                   This helps with proper nouns, technical terms, and style.
        """
        if not self.client:
            raise GroqClientError("API Key not set.")

        try:
            # Handle both BytesIO (in-memory) and file paths
            if hasattr(file_source, "read"):
                # In-memory BytesIO buffer - read and create tuple
                audio_data = file_source.read()
                file_tuple = ("audio.wav", audio_data)
                logger.info(f"Transcribing from memory buffer: {len(audio_data)} bytes")
            else:
                # File path - open and read
                with open(file_source, "rb") as f:
                    audio_data = f.read()
                file_tuple = (file_source, audio_data)
                logger.info(f"Transcribing from file: {file_source}")

            # Build transcription parameters
            params = {
                "file": file_tuple,
                "model": model_id,
                "response_format": "json",
                "language": "en",
                "temperature": 0.0
            }

            # Add prompt if provided - helps with accuracy for:
            # - Proper nouns and technical terms
            # - Consistent punctuation and capitalization
            # - Context from previous transcriptions
            if prompt:
                params["prompt"] = prompt

            transcription = self.client.audio.transcriptions.create(**params)
            return str(transcription.text)
        except APIStatusError as e:
            raise GroqClientError(f"API Error: {e.message}")
        except Exception as e:
            raise GroqClientError(f"Transcription failed: {e}")

    def format_text(self, raw_text: str, model_id: str = "openai/gpt-oss-120b", system_prompt: Optional[str] = None) -> str:
        if not self.client:
            raise GroqClientError("API Key not set.")

        prompt = system_prompt if system_prompt else SYSTEM_PROMPT_FORMATTER

        try:
            completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": raw_text
                    }
                ],
                model=model_id,
                temperature=0.3,
            )
            return str(completion.choices[0].message.content)
        except Exception as e:
            raise GroqClientError(f"Formatting failed: {e}")

    def run_search(self, query: str) -> str:
        if not self.client:
            raise GroqClientError("API Key not set.")

        try:
            from src.prompts import SYSTEM_PROMPT_SEARCH

            # Using 'groq/compound' which has native tool use capabilities (search)
            # The model decides when to search based on the query.
            completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT_SEARCH
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                model="groq/compound",
                temperature=0.0
            )
            return str(completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"Search Error: {str(e)}"
