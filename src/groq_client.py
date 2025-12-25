import os
import logging
from groq import Groq, APIConnectionError, APIStatusError
from src.prompts import SYSTEM_PROMPT_FORMATTER

# Configure logger
logger = logging.getLogger(__name__)

class GroqClientError(Exception):
    """Custom exception for Groq Client errors."""
    pass

class GroqClient:
    def __init__(self, api_key):
        self.client = None
        if api_key:
            self.update_api_key(api_key)

    def update_api_key(self, api_key):
        try:
            clean_key = api_key.strip() if api_key else ""
            self.client = Groq(api_key=clean_key)
        except Exception as e:
            logger.error(f"Error initializing Groq client: {e}")
            self.client = None

    def check_connection(self):
        if not self.client:
            return False
        try:
            self.client.models.list()
            return True
        except Exception:
            return False

    def list_models(self):
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

    def transcribe(self, file_path, model_id="whisper-large-v3"):
        if not self.client:
            raise GroqClientError("API Key not set.")

        try:
            with open(file_path, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=(file_path, file.read()),
                    model=model_id,
                    response_format="json",
                    language="en", 
                    temperature=0.0 
                )
            return transcription.text
        except APIStatusError as e:
            raise GroqClientError(f"API Error: {e.message}")
        except Exception as e:
            raise GroqClientError(f"Transcription failed: {e}")

    def format_text(self, raw_text, model_id="llama3-70b-8192"):
        if not self.client:
            raise GroqClientError("API Key not set.")

        try:
            completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT_FORMATTER
                    },
                    {
                        "role": "user",
                        "content": raw_text
                    }
                ],
                model=model_id,
                temperature=0.3,
            )
            return completion.choices[0].message.content
        except Exception as e:
            raise GroqClientError(f"Formatting failed: {e}")