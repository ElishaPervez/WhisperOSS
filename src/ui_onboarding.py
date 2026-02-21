from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class _SetupDialogBase(QDialog):
    """Shared shell for first-run onboarding dialogs."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedWidth(520)

        self.setStyleSheet(
            """
            QDialog {
                background: #f1f5f9;
                color: #0f172a;
                font-family: 'Segoe UI Variable';
                font-size: 13px;
            }

            QFrame#SetupCard {
                border: 1px solid #cbd5e1;
                border-radius: 14px;
                background: #ffffff;
            }

            QLabel#Badge {
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                border-radius: 14px;
                color: #ffffff;
                font-weight: 700;
                font-size: 14px;
                qproperty-alignment: AlignCenter;
            }

            QLabel#Heading {
                font-size: 19px;
                font-weight: 700;
                color: #0f172a;
            }

            QLabel#Body {
                color: #334155;
                font-size: 13px;
                line-height: 1.4;
            }

            QLabel#Label {
                color: #475569;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }

            QLabel#Link {
                color: #0284c7;
                font-size: 12px;
            }

            QLabel#InlineError {
                color: #b91c1c;
                font-size: 12px;
                font-weight: 600;
            }

            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                padding: 10px 12px;
                min-height: 22px;
                background: #ffffff;
                color: #0f172a;
            }

            QLineEdit:focus {
                border: 1px solid #0ea5e9;
            }

            QPushButton {
                border-radius: 10px;
                padding: 8px 14px;
                min-width: 96px;
                font-weight: 600;
            }

            QPushButton#SecondaryButton {
                border: 1px solid #cbd5e1;
                color: #334155;
                background: #f8fafc;
            }

            QPushButton#SecondaryButton:hover {
                border: 1px solid #94a3b8;
                background: #f1f5f9;
            }

            QPushButton#PrimaryButton {
                border: 1px solid #0369a1;
                color: #ffffff;
                background: #0284c7;
            }

            QPushButton#PrimaryButton:hover {
                border: 1px solid #075985;
                background: #0369a1;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("SetupCard")
        root.addWidget(self.card)

        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(18, 18, 18, 16)
        self.card_layout.setSpacing(14)

    @staticmethod
    def _badge_style(severity: str) -> str:
        if severity == "warning":
            return "background: #d97706;"
        if severity == "error":
            return "background: #dc2626;"
        return "background: #0284c7;"

    def _add_header(self, heading: str, severity: str) -> None:
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        badge = QLabel("i")
        badge.setObjectName("Badge")
        badge.setStyleSheet(self._badge_style(severity))
        header_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        heading_label = QLabel(heading)
        heading_label.setObjectName("Heading")
        heading_label.setWordWrap(True)
        header_row.addWidget(heading_label, 1)

        self.card_layout.addLayout(header_row)

    def _add_body(self, text: str) -> None:
        body_label = QLabel(text)
        body_label.setObjectName("Body")
        body_label.setWordWrap(True)
        self.card_layout.addWidget(body_label)

    def _add_button_row(
        self,
        primary_text: str,
        secondary_text: str | None = None,
        primary_handler=None,
        secondary_handler=None,
    ) -> QPushButton:
        buttons = QHBoxLayout()
        buttons.addStretch()

        if secondary_text:
            secondary = QPushButton(secondary_text)
            secondary.setObjectName("SecondaryButton")
            secondary.clicked.connect(secondary_handler or self.reject)
            buttons.addWidget(secondary)

        primary = QPushButton(primary_text)
        primary.setObjectName("PrimaryButton")
        primary.clicked.connect(primary_handler or self.accept)
        primary.setDefault(True)
        buttons.addWidget(primary)

        self.card_layout.addLayout(buttons)
        return primary


class SetupMessageDialog(_SetupDialogBase):
    """Simple information/warning dialog with polished first-run styling."""

    def __init__(
        self,
        title: str,
        heading: str,
        body: str,
        severity: str = "info",
        primary_text: str = "OK",
        secondary_text: str | None = None,
        parent=None,
    ):
        super().__init__(title, parent=parent)
        self._add_header(heading, severity)
        self._add_body(body)
        self._add_button_row(primary_text, secondary_text)
        self.adjustSize()


class ApiKeyInputDialog(_SetupDialogBase):
    """Guided API key input with inline validation feedback."""

    def __init__(self, initial_key: str = "", parent=None):
        super().__init__("Connect Groq API", parent=parent)

        self._add_header("Connect your Groq API key", "info")
        self._add_body(
            "WhisperOSS uses Groq for transcription. "
            "Paste your key below to activate voice typing."
        )

        label = QLabel("Groq API Key")
        label.setObjectName("Label")
        self.card_layout.addWidget(label)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("gsk_...")
        self.key_input.setText(initial_key)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.textChanged.connect(self._clear_inline_error)
        input_row.addWidget(self.key_input, 1)

        self.toggle_button = QPushButton("Show")
        self.toggle_button.setObjectName("SecondaryButton")
        self.toggle_button.setFixedWidth(74)
        self.toggle_button.clicked.connect(self._toggle_key_visibility)
        input_row.addWidget(self.toggle_button)

        self.card_layout.addLayout(input_row)

        link = QLabel('<a href="https://console.groq.com/keys">Open Groq Console</a>')
        link.setObjectName("Link")
        link.setTextFormat(Qt.TextFormat.RichText)
        link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        link.setOpenExternalLinks(True)
        self.card_layout.addWidget(link)

        self.inline_error = QLabel("")
        self.inline_error.setObjectName("InlineError")
        self.inline_error.hide()
        self.card_layout.addWidget(self.inline_error)

        self._add_button_row(
            primary_text="Connect",
            secondary_text="Exit",
            primary_handler=self._on_submit,
            secondary_handler=self.reject,
        )
        self.adjustSize()
        self.key_input.setFocus()

    def _toggle_key_visibility(self) -> None:
        showing = self.key_input.echoMode() == QLineEdit.EchoMode.Normal
        if showing:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_button.setText("Show")
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_button.setText("Hide")

    def _clear_inline_error(self) -> None:
        self.inline_error.hide()

    def _on_submit(self) -> None:
        if not self.api_key():
            self.inline_error.setText("Enter a valid Groq API key to continue.")
            self.inline_error.show()
            return
        self.accept()

    def api_key(self) -> str:
        return self.key_input.text().strip()
