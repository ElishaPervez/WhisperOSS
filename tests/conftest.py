import pytest
import sys
import os

# Add src to the path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

@pytest.fixture
def mock_config():
    """Returns a default configuration dictionary."""
    return {
        "api_key": "test_api_key",
        "input_device_index": 0,
        "formatting_enabled": True
    }
