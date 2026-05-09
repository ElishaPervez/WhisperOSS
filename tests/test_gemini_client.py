import types as pytypes
from unittest.mock import MagicMock

import pytest

from src.gemini_client import GeminiClient, GeminiClientError


class _FakeGenerateContentConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeThinkingConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeTool:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeGoogleSearch:
    pass


class _FakePart:
    @staticmethod
    def from_bytes(*, data, mime_type):
        return {"kind": "bytes", "data": data, "mime_type": mime_type}


@pytest.fixture
def fake_sdk_modules():
    fake_types = pytypes.SimpleNamespace(
        GenerateContentConfig=_FakeGenerateContentConfig,
        ThinkingConfig=_FakeThinkingConfig,
        Tool=_FakeTool,
        GoogleSearch=_FakeGoogleSearch,
        Part=_FakePart,
    )
    fake_genai = pytypes.SimpleNamespace(Client=MagicMock())
    return fake_genai, fake_types


def test_init_with_key_builds_sdk_client(fake_sdk_modules):
    fake_genai, fake_types = fake_sdk_modules

    class ClientUnderTest(GeminiClient):
        def _load_sdk_modules(self):
            return fake_genai, fake_types

    client = ClientUnderTest(api_key="gem-key")

    fake_genai.Client.assert_called_once_with(api_key="gem-key")
    assert client.client is fake_genai.Client.return_value


def test_list_models_returns_sorted_generate_content_models(fake_sdk_modules):
    fake_genai, fake_types = fake_sdk_modules
    sdk_client = fake_genai.Client.return_value
    sdk_client.models.list.return_value = [
        pytypes.SimpleNamespace(name="models/embed-only", supported_generation_methods=["embedContent"]),
        pytypes.SimpleNamespace(name="models/gemma-4-31b-it", supported_generation_methods=["generateContent"]),
        pytypes.SimpleNamespace(name="models/gemini-2.5-flash", supported_generation_methods=["generateContent", "countTokens"]),
    ]

    class ClientUnderTest(GeminiClient):
        def _load_sdk_modules(self):
            return fake_genai, fake_types

    client = ClientUnderTest(api_key="gem-key")

    assert client.list_models() == ["models/gemini-2.5-flash", "models/gemma-4-31b-it"]


def test_list_models_supports_sdk_supported_actions_shape(fake_sdk_modules):
    fake_genai, fake_types = fake_sdk_modules
    sdk_client = fake_genai.Client.return_value
    sdk_client.models.list.return_value = [
        pytypes.SimpleNamespace(name="models/gemma-4-31b-it", supported_actions=["generateContent", "countTokens"]),
        pytypes.SimpleNamespace(name="models/gemini-embedding-001", supported_actions=["embedContent"]),
    ]

    class ClientUnderTest(GeminiClient):
        def _load_sdk_modules(self):
            return fake_genai, fake_types

    client = ClientUnderTest(api_key="gem-key")

    assert client.list_models() == ["models/gemma-4-31b-it"]


def test_run_search_uses_grounding_and_streams_cumulative_text(fake_sdk_modules):
    fake_genai, fake_types = fake_sdk_modules
    sdk_client = fake_genai.Client.return_value
    sdk_client.models.generate_content_stream.return_value = [
        pytypes.SimpleNamespace(text="Hello"),
        pytypes.SimpleNamespace(text=" world"),
        pytypes.SimpleNamespace(text=None),
    ]
    streamed = []

    class ClientUnderTest(GeminiClient):
        def _load_sdk_modules(self):
            return fake_genai, fake_types

    client = ClientUnderTest(api_key="gem-key")

    result = client.run_search(
        query="What is DNS?",
        model_id="models/gemma-4-31b-it",
        system_prompt="Be concise",
        stream_callback=streamed.append,
    )

    assert result == "Hello world"
    assert streamed == ["Hello", "Hello world"]

    kwargs = sdk_client.models.generate_content_stream.call_args.kwargs
    assert kwargs["model"] == "models/gemma-4-31b-it"
    assert kwargs["contents"] == "What is DNS?"
    config = kwargs["config"]
    assert config.kwargs["system_instruction"] == "Be concise"
    assert len(config.kwargs["tools"]) == 1
    assert isinstance(config.kwargs["tools"][0], _FakeTool)
    assert isinstance(config.kwargs["tools"][0].kwargs["google_search"], _FakeGoogleSearch)
    assert isinstance(config.kwargs["thinking_config"], _FakeThinkingConfig)


def test_run_search_separates_thought_parts_from_answer_stream(fake_sdk_modules):
    fake_genai, fake_types = fake_sdk_modules
    sdk_client = fake_genai.Client.return_value
    sdk_client.models.generate_content_stream.return_value = [
        pytypes.SimpleNamespace(
            text=None,
            candidates=[
                pytypes.SimpleNamespace(
                    content=pytypes.SimpleNamespace(
                        parts=[
                            pytypes.SimpleNamespace(text="I will check the facts. ", thought=True),
                            pytypes.SimpleNamespace(text="", thought=False),
                        ],
                    ),
                ),
            ],
        ),
        pytypes.SimpleNamespace(
            text=None,
            candidates=[
                pytypes.SimpleNamespace(
                    content=pytypes.SimpleNamespace(
                        parts=[
                            pytypes.SimpleNamespace(text="Paris", thought=False),
                        ],
                    ),
                ),
            ],
        ),
        pytypes.SimpleNamespace(
            text=None,
            candidates=[
                pytypes.SimpleNamespace(
                    content=pytypes.SimpleNamespace(
                        parts=[
                            pytypes.SimpleNamespace(text=" is the capital.", thought=False),
                        ],
                    ),
                ),
            ],
        ),
    ]
    streamed = []
    thoughts = []

    class ClientUnderTest(GeminiClient):
        def _load_sdk_modules(self):
            return fake_genai, fake_types

    client = ClientUnderTest(api_key="gem-key")

    result = client.run_search(
        query="Capital of France?",
        model_id="models/gemma-4-31b-it",
        stream_callback=streamed.append,
        thought_callback=thoughts.append,
    )

    assert result == "Paris is the capital."
    assert streamed == ["Paris", "Paris is the capital."]
    assert thoughts == ["I will check the facts. "]


def test_run_search_includes_inline_image_bytes(fake_sdk_modules):
    fake_genai, fake_types = fake_sdk_modules
    sdk_client = fake_genai.Client.return_value
    sdk_client.models.generate_content_stream.return_value = [
        pytypes.SimpleNamespace(text="This is a save button.")
    ]

    class ClientUnderTest(GeminiClient):
        def _load_sdk_modules(self):
            return fake_genai, fake_types

    client = ClientUnderTest(api_key="gem-key")

    result = client.run_search(
        query="What is this?",
        model_id="models/gemma-4-31b-it",
        image_bytes=b"\x89PNG\r\n",
    )

    assert result == "This is a save button."
    kwargs = sdk_client.models.generate_content_stream.call_args.kwargs
    assert kwargs["contents"][0] == "What is this?"
    assert kwargs["contents"][1]["kind"] == "bytes"
    assert kwargs["contents"][1]["mime_type"] == "image/png"


def test_run_search_raises_when_sdk_fails(fake_sdk_modules):
    fake_genai, fake_types = fake_sdk_modules
    sdk_client = fake_genai.Client.return_value
    sdk_client.models.generate_content_stream.side_effect = RuntimeError("boom")

    class ClientUnderTest(GeminiClient):
        def _load_sdk_modules(self):
            return fake_genai, fake_types

    client = ClientUnderTest(api_key="gem-key")

    with pytest.raises(GeminiClientError, match="boom"):
        client.run_search(query="hello", model_id="models/gemma-4-31b-it")
