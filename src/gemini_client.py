import importlib
import logging
from typing import Callable, Optional


logger = logging.getLogger(__name__)


class GeminiClientError(Exception):
    """Raised when Gemini API operations fail."""


class GeminiClient:
    def __init__(self, api_key: Optional[str]):
        self.client = None
        self._types = None
        if api_key:
            self.update_api_key(api_key)

    def _load_sdk_modules(self):
        try:
            genai = importlib.import_module("google.genai")
            types_mod = importlib.import_module("google.genai.types")
            return genai, types_mod
        except Exception as exc:  # pragma: no cover - environment dependent
            raise GeminiClientError(
                "Gemini SDK not installed. Install `google-genai` to enable Gemini search."
            ) from exc

    def update_api_key(self, api_key: str) -> None:
        normalized = str(api_key or "").strip()
        if not normalized:
            self.client = None
            self._types = None
            return

        try:
            genai, types_mod = self._load_sdk_modules()
            self.client = genai.Client(api_key=normalized)
            self._types = types_mod
        except Exception as exc:
            logger.error("Failed to initialize Gemini client: %s", exc)
            self.client = None
            self._types = None
            raise

    def check_connection(self) -> bool:
        try:
            return bool(self.list_models())
        except Exception:
            return False

    def list_models(self) -> list[str]:
        if self.client is None:
            return []

        try:
            model_ids: list[str] = []
            for model in self.client.models.list():
                name = str(getattr(model, "name", "") or "").strip()
                if not name:
                    continue
                methods = getattr(model, "supported_generation_methods", None)
                if methods is None:
                    methods = getattr(model, "supportedGenerationMethods", None)
                if methods is None:
                    methods = getattr(model, "supported_actions", None)
                methods = [str(item) for item in (methods or [])]
                if "generateContent" in methods:
                    model_ids.append(name)
            return sorted(set(model_ids))
        except Exception as exc:
            raise GeminiClientError(f"Failed to list Gemini models: {exc}") from exc

    def run_search(
        self,
        query: str,
        model_id: str,
        system_prompt: str = "",
        image_bytes: Optional[bytes] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        thought_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        if self.client is None or self._types is None:
            raise GeminiClientError("Gemini API key not set.")

        cleaned_query = str(query or "").strip()
        if not cleaned_query:
            raise GeminiClientError("Empty Gemini query.")

        config = self._types.GenerateContentConfig(
            system_instruction=str(system_prompt or "").strip() or None,
            tools=[self._types.Tool(google_search=self._types.GoogleSearch())],
            thinking_config=self._types.ThinkingConfig(thinking_level="high"),
        )

        contents: object = cleaned_query
        if image_bytes:
            contents = [
                cleaned_query,
                self._types.Part.from_bytes(data=bytes(image_bytes), mime_type="image/png"),
            ]

        try:
            final_text = ""
            for chunk in self.client.models.generate_content_stream(
                model=str(model_id or "").strip(),
                contents=contents,
                config=config,
            ):
                saw_parts = False
                for candidate in getattr(chunk, "candidates", None) or []:
                    content = getattr(candidate, "content", None)
                    for part in getattr(content, "parts", None) or []:
                        saw_parts = True
                        text = str(getattr(part, "text", "") or "")
                        if not text:
                            continue
                        if bool(getattr(part, "thought", False)):
                            if thought_callback is not None:
                                thought_callback(text)
                            continue
                        final_text += text
                        if stream_callback is not None:
                            stream_callback(final_text)

                if saw_parts:
                    continue

                text = str(getattr(chunk, "text", "") or "")
                if text:
                    final_text += text
                    if stream_callback is not None:
                        stream_callback(final_text)
            return final_text.strip()
        except Exception as exc:
            raise GeminiClientError(f"Gemini search failed: {exc}") from exc
