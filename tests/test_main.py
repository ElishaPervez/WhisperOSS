from unittest.mock import patch
from src.main import main as entry_point


def test_main_creates_controller_and_calls_run():
    """main() must instantiate WhisperAppController and call run() exactly once."""
    with patch("src.main.WhisperAppController") as mock_controller_cls, \
         patch("src.main.QApplication"):
        entry_point()

        mock_controller_cls.assert_called_once()
        mock_controller_cls.return_value.run.assert_called_once()
