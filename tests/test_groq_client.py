import pytest
from unittest.mock import MagicMock, patch, mock_open
from src.groq_client import GroqClient, GroqClientError

@pytest.fixture
def mock_groq_package():
    with patch("src.groq_client.Groq") as mock_groq:
        yield mock_groq

def test_init_with_key(mock_groq_package):
    client = GroqClient(api_key="test_key")
    mock_groq_package.assert_called_once_with(api_key="test_key")
    assert client.client is not None

def test_init_without_key(mock_groq_package):
    client = GroqClient(api_key=None)
    mock_groq_package.assert_not_called()
    assert client.client is None

def test_check_connection_success(mock_groq_package):
    client = GroqClient("key")
    mock_instance = mock_groq_package.return_value
    mock_instance.models.list.return_value = MagicMock()
    assert client.check_connection() is True

def test_check_connection_fail_no_client():
    client = GroqClient(None)
    assert client.check_connection() is False

def test_check_connection_fail_api(mock_groq_package):
    client = GroqClient("key")
    mock_instance = mock_groq_package.return_value
    mock_instance.models.list.side_effect = Exception("Fail")
    assert client.check_connection() is False

def test_list_models_success(mock_groq_package):
    client = GroqClient("key")
    mock_instance = mock_groq_package.return_value
    
    # Mock model data
    m1 = MagicMock(); m1.id = "whisper-large-v3"
    m2 = MagicMock(); m2.id = "llama3-70b-8192"
    mock_instance.models.list.return_value.data = [m1, m2]
    
    transcription, llm = client.list_models()
    assert "whisper-large-v3" in transcription
    assert "llama3-70b-8192" in llm

def test_list_models_fail(mock_groq_package):
    client = GroqClient("key")
    mock_instance = mock_groq_package.return_value
    mock_instance.models.list.side_effect = Exception("Fail")
    
    t, l = client.list_models()
    assert t == []
    assert l == []

def test_transcribe_success(mock_groq_package):
    client = GroqClient("key")
    mock_instance = mock_groq_package.return_value
    
    mock_transcription = MagicMock()
    mock_transcription.text = "Hello world"
    mock_instance.audio.transcriptions.create.return_value = mock_transcription
    
    with patch("builtins.open", mock_open(read_data=b"audio data")):
        result = client.transcribe("dummy.wav")
        
    assert result == "Hello world"

def test_transcribe_api_error(mock_groq_package):
    client = GroqClient("key")
    mock_instance = mock_groq_package.return_value
    # Simulate an API error
    mock_instance.audio.transcriptions.create.side_effect = Exception("API Down")
    
    with patch("builtins.open", mock_open(read_data=b"audio data")):
        with pytest.raises(GroqClientError, match="Transcription failed: API Down"):
            client.transcribe("dummy.wav")

def test_format_text_success(mock_groq_package):
    client = GroqClient("key")
    mock_instance = mock_groq_package.return_value
    
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "Formatted"
    mock_instance.chat.completions.create.return_value = mock_completion
    
    assert client.format_text("raw") == "Formatted"

def test_format_text_error(mock_groq_package):
    client = GroqClient("key")
    mock_instance = mock_groq_package.return_value
    mock_instance.chat.completions.create.side_effect = Exception("Format Fail")
    
    with pytest.raises(GroqClientError, match="Formatting failed: Format Fail"):
        client.format_text("raw")
