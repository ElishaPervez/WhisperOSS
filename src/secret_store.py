import logging


logger = logging.getLogger(__name__)

SERVICE_NAME = "WhisperOSS"
ACCOUNT_NAME = "groq_api_key"


class ApiKeyStore:
    """Store API keys in OS credential storage when available."""

    def __init__(self, service_name: str = SERVICE_NAME, account_name: str = ACCOUNT_NAME):
        self.service_name = service_name
        self.account_name = account_name
        self._keyring = None
        self._load_keyring()

    def _load_keyring(self) -> None:
        try:
            import keyring  # type: ignore

            self._keyring = keyring
        except Exception:
            self._keyring = None

    @property
    def is_available(self) -> bool:
        return self._keyring is not None

    def get_api_key(self) -> str:
        if not self.is_available:
            return ""

        try:
            value = self._keyring.get_password(self.service_name, self.account_name)
            return value or ""
        except Exception as exc:
            logger.warning(f"Secure credential read failed: {exc}")
            return ""

    def set_api_key(self, api_key: str) -> bool:
        if not self.is_available:
            return False

        try:
            self._keyring.set_password(self.service_name, self.account_name, api_key)
            return True
        except Exception as exc:
            logger.warning(f"Secure credential write failed: {exc}")
            return False

    def clear_api_key(self) -> bool:
        if not self.is_available:
            return True

        try:
            self._keyring.delete_password(self.service_name, self.account_name)
            return True
        except Exception:
            # Deleting a non-existent credential is treated as success.
            return True
