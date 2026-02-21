from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QPropertyAnimation,
    QEasingCurve,
    QTimer,
    QPoint,
    QPointF,
    QLineF,
    QSize,
    pyqtProperty,
    QEvent,
)
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QLinearGradient, QRadialGradient, QFont, QPalette, QCursor
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QFrame,
)


def _is_dark_theme_widget(widget):
    current = widget
    while current is not None:
        if hasattr(current, "_is_dark_theme"):
            return bool(getattr(current, "_is_dark_theme"))
        current = current.parentWidget()
    return False


class AnimatedToggle(QCheckBox):
    """Compact animated toggle switch used for boolean settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 28)
        self._handle_position = 4.0
        self._animation = QPropertyAnimation(self, b"handle_position", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.stateChanged.connect(self._animate)

    def _animate(self, state):
        self._animation.setEndValue(self.width() - 24 if state else 4)
        self._animation.start()

    def _get_handle_position(self):
        return self._handle_position

    def _set_handle_position(self, pos):
        self._handle_position = pos
        self.update()

    handle_position = pyqtProperty(float, _get_handle_position, _set_handle_position)

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark_theme = _is_dark_theme_widget(self)

        if self.isEnabled():
            if self.isChecked():
                track_color = QColor("#22c55e") if dark_theme else QColor("#0ea5e9")
            else:
                track_color = QColor("#334155") if dark_theme else QColor("#cbd5e1")
        else:
            track_color = QColor("#1f2937") if dark_theme else QColor("#e2e8f0")

        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)

        handle_color = QColor("#e2e8f0") if dark_theme else QColor("#ffffff")
        painter.setBrush(QBrush(handle_color))
        painter.drawEllipse(int(self._handle_position), 4, 20, 20)


class GlassPanel(QFrame):
    """Card surface with subtle depth and border to create desktop-grade grouping."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark_theme = _is_dark_theme_widget(self)

        card_name = self.objectName()
        if dark_theme:
            if card_name == "HeroCard":
                top = QColor(15, 23, 42, 230)
                bottom = QColor(2, 6, 23, 220)
                border = QColor(34, 197, 94, 96)
            elif card_name == "SettingsCard":
                top = QColor(15, 23, 42, 236)
                bottom = QColor(2, 6, 23, 230)
                border = QColor(45, 212, 191, 94)
            elif card_name == "StatCard":
                top = QColor(30, 41, 59, 228)
                bottom = QColor(15, 23, 42, 220)
                border = QColor(34, 197, 94, 84)
            else:
                top = QColor(15, 23, 42, 228)
                bottom = QColor(2, 6, 23, 220)
                border = QColor(45, 212, 191, 88)
        else:
            if card_name == "HeroCard":
                top = QColor(255, 255, 255, 220)
                bottom = QColor(241, 245, 249, 214)
                border = QColor(148, 163, 184, 80)
            elif card_name == "SettingsCard":
                top = QColor(255, 255, 255, 232)
                bottom = QColor(248, 250, 252, 228)
                border = QColor(148, 163, 184, 88)
            elif card_name == "StatCard":
                top = QColor(248, 250, 252, 220)
                bottom = QColor(241, 245, 249, 214)
                border = QColor(148, 163, 184, 76)
            else:
                top = QColor(255, 255, 255, 220)
                bottom = QColor(241, 245, 249, 216)
                border = QColor(148, 163, 184, 80)

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, bottom)

        painter.setPen(QPen(border, 1))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)


class MainWindow(QWidget):
    # Signals to Main Controller
    record_toggled = pyqtSignal(bool)  # True=Start, False=Stop
    config_changed = pyqtSignal(str, object)  # key, value

    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self.setWindowTitle("WhisperOSS Settings")
        self.resize(960, 640)
        self.setMinimumSize(QSize(860, 560))

        self._blur_active = False
        self._dragging = False
        self.oldPos = self.pos()
        self._resizing = False
        self._resize_margin = 8
        self._resize_edges = 0
        self._press_global_pos = QPoint()
        self._press_geometry = self.geometry()
        self._appearance_mode = self._normalize_appearance_mode(self.config.get("appearance_mode", "auto"))
        self._is_dark_theme = self._resolve_dark_theme()

        # Frameless layout keeps this feeling like a polished desktop app shell.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)

        self._apply_blur_effect()
        self._setup_styling()

        self.is_recording = False
        self.setup_ui()
        self._init_ui_state()

    def _apply_blur_effect(self):
        """Apply Windows acrylic blur when available."""
        try:
            from src.window_effects import WindowEffect

            self._window_effect = WindowEffect()

            def apply_and_track():
                self._blur_active = self._window_effect.set_acrylic(self.winId())
                self._window_effect.set_rounded_corners(self.winId())
                if self._blur_active:
                    self.update()

            QTimer.singleShot(100, apply_and_track)
        except ImportError:
            self._blur_active = False

    def _normalize_appearance_mode(self, mode):
        normalized = str(mode or "auto").strip().lower()
        return normalized if normalized in {"auto", "dark", "light"} else "auto"

    def _resolve_dark_theme(self):
        if self._appearance_mode == "dark":
            return True
        if self._appearance_mode == "light":
            return False

        app = QApplication.instance()
        if app is None:
            return False

        palette = app.palette()
        base = palette.color(QPalette.ColorRole.Window)
        text = palette.color(QPalette.ColorRole.WindowText)
        return base.lightness() < text.lightness()

    def _refresh_theme_widgets(self):
        for widget in (self.status_label, self.api_key_hint):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

        for widget in (
            self.hero_card,
            self.stats_row,
            self.connection_card,
            self.settings_card,
            self.format_toggle,
            self.translation_toggle,
        ):
            widget.update()

    def _setup_styling(self):
        base_stylesheet = """
            QWidget {
                background: transparent;
                color: #0f172a;
                font-family: 'Segoe UI Variable';
                font-size: 13px;
            }

            QFrame#HeaderBar {
                border: 1px solid rgba(148, 163, 184, 0.38);
                border-radius: 16px;
                background: rgba(255, 255, 255, 0.78);
            }

            QLabel#WindowTitle {
                font-size: 23px;
                font-weight: 700;
                color: #0b1220;
            }

            QLabel#Subtitle {
                font-size: 12px;
                color: #475569;
                font-weight: 500;
                letter-spacing: 0.2px;
            }

            QLabel#StatusBadge {
                font-size: 11px;
                font-weight: 600;
                border-radius: 12px;
                padding: 6px 10px;
                background: #e2e8f0;
                color: #334155;
                border: 1px solid #cbd5e1;
            }

            QLabel#StatusBadge[state='ok'] {
                background: #dcfce7;
                border: 1px solid #86efac;
                color: #166534;
            }

            QLabel#StatusBadge[state='error'] {
                background: #fee2e2;
                border: 1px solid #fca5a5;
                color: #991b1b;
            }

            QLabel#StatusBadge[state='active'] {
                background: #e0f2fe;
                border: 1px solid #7dd3fc;
                color: #075985;
            }

            QPushButton#TitleBtn,
            QPushButton#CloseBtn {
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                border-radius: 15px;
                border: 1px solid #cbd5e1;
                background: #ffffff;
                color: #334155;
                font-size: 16px;
                font-weight: 700;
            }

            QPushButton#TitleBtn:hover {
                background: #f8fafc;
                border: 1px solid #94a3b8;
            }

            QPushButton#CloseBtn:hover {
                background: #fee2e2;
                border: 1px solid #fca5a5;
                color: #b91c1c;
            }

            QLabel#HeroTitle {
                font-size: 22px;
                font-weight: 700;
                color: #0f172a;
            }

            QLabel#MutedText {
                color: #475569;
                font-size: 12px;
                font-weight: 500;
            }

            QLabel#CardTitle {
                font-size: 14px;
                font-weight: 700;
                color: #0f172a;
                letter-spacing: 0.3px;
            }

            QLabel#SectionCaption {
                color: #64748b;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.8px;
                text-transform: uppercase;
            }

            QLabel#StatTitle {
                color: #64748b;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.4px;
            }

            QLabel#StatValue {
                color: #0f172a;
                font-size: 14px;
                font-weight: 700;
            }

            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                padding: 8px 10px;
                min-height: 22px;
                background: rgba(255, 255, 255, 0.94);
                color: #0f172a;
            }

            QComboBox:hover {
                border: 1px solid #94a3b8;
            }

            QComboBox:focus {
                border: 1px solid #0ea5e9;
            }

            QComboBox::drop-down {
                border: none;
                width: 20px;
            }

            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #64748b;
                margin-right: 6px;
            }

            QComboBox QAbstractItemView {
                border: 1px solid #cbd5e1;
                background: #ffffff;
                selection-background-color: #0ea5e9;
                selection-color: #ffffff;
                color: #0f172a;
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }

            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                padding: 8px 10px;
                min-height: 22px;
                background: rgba(255, 255, 255, 0.94);
                color: #0f172a;
            }

            QLineEdit:focus {
                border: 1px solid #0ea5e9;
            }

            QPushButton#SoftButton {
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                background: #f8fafc;
                color: #334155;
                min-height: 22px;
                padding: 8px 12px;
                font-weight: 600;
            }

            QPushButton#SoftButton:hover {
                border: 1px solid #94a3b8;
                background: #f1f5f9;
            }

            QPushButton#PrimaryAction {
                border: 1px solid #0369a1;
                border-radius: 10px;
                background: #0284c7;
                color: #ffffff;
                min-height: 22px;
                padding: 8px 12px;
                font-weight: 700;
            }

            QPushButton#PrimaryAction:hover {
                border: 1px solid #075985;
                background: #0369a1;
            }

            QPushButton#PrimaryAction:disabled {
                border: 1px solid #94a3b8;
                background: #94a3b8;
                color: #e2e8f0;
            }

            QLabel#ApiHint {
                color: #475569;
                font-size: 12px;
                font-weight: 600;
            }

            QLabel#ApiHint[state='ok'] {
                color: #166534;
            }

            QLabel#ApiHint[state='error'] {
                color: #b91c1c;
            }

            QFrame#Divider {
                min-height: 1px;
                max-height: 1px;
                background: rgba(148, 163, 184, 0.34);
            }
            """

        dark_overrides = """
            QWidget {
                color: #e2e8f0;
            }

            QFrame#HeaderBar {
                border: 1px solid rgba(45, 212, 191, 0.42);
                background: rgba(2, 6, 23, 0.78);
            }

            QLabel#WindowTitle {
                color: #ecfeff;
            }

            QLabel#Subtitle {
                color: #94a3b8;
            }

            QLabel#StatusBadge {
                background: #0f172a;
                color: #cbd5e1;
                border: 1px solid #334155;
            }

            QLabel#StatusBadge[state='ok'] {
                background: #052e16;
                border: 1px solid #15803d;
                color: #86efac;
            }

            QLabel#StatusBadge[state='error'] {
                background: #450a0a;
                border: 1px solid #b91c1c;
                color: #fecaca;
            }

            QLabel#StatusBadge[state='active'] {
                background: #0c4a6e;
                border: 1px solid #0284c7;
                color: #bae6fd;
            }

            QPushButton#TitleBtn,
            QPushButton#CloseBtn {
                border: 1px solid #334155;
                background: #0f172a;
                color: #cbd5e1;
            }

            QPushButton#TitleBtn:hover {
                background: #1e293b;
                border: 1px solid #475569;
            }

            QPushButton#CloseBtn:hover {
                background: #7f1d1d;
                border: 1px solid #b91c1c;
                color: #fee2e2;
            }

            QLabel#HeroTitle,
            QLabel#CardTitle,
            QLabel#StatValue {
                color: #f8fafc;
            }

            QLabel#MutedText {
                color: #94a3b8;
            }

            QLabel#SectionCaption,
            QLabel#StatTitle {
                color: #7dd3fc;
            }

            QComboBox {
                border: 1px solid #334155;
                background: rgba(2, 6, 23, 0.90);
                color: #e2e8f0;
            }

            QComboBox:hover {
                border: 1px solid #0ea5e9;
            }

            QComboBox:focus {
                border: 1px solid #22c55e;
            }

            QComboBox::down-arrow {
                border-top: 6px solid #94a3b8;
            }

            QComboBox QAbstractItemView {
                border: 1px solid #334155;
                background: #020617;
                selection-background-color: #166534;
                selection-color: #ecfdf5;
                color: #e2e8f0;
            }

            QLineEdit {
                border: 1px solid #334155;
                background: rgba(2, 6, 23, 0.90);
                color: #e2e8f0;
            }

            QLineEdit:focus {
                border: 1px solid #22c55e;
            }

            QPushButton#SoftButton {
                border: 1px solid #334155;
                background: #0f172a;
                color: #cbd5e1;
            }

            QPushButton#SoftButton:hover {
                border: 1px solid #475569;
                background: #1e293b;
            }

            QPushButton#PrimaryAction {
                border: 1px solid #166534;
                background: #15803d;
                color: #f0fdf4;
            }

            QPushButton#PrimaryAction:hover {
                border: 1px solid #22c55e;
                background: #166534;
            }

            QPushButton#PrimaryAction:disabled {
                border: 1px solid #334155;
                background: #1e293b;
                color: #64748b;
            }

            QLabel#ApiHint {
                color: #93c5fd;
            }

            QLabel#ApiHint[state='ok'] {
                color: #86efac;
            }

            QLabel#ApiHint[state='error'] {
                color: #fca5a5;
            }

            QFrame#Divider {
                background: rgba(51, 65, 85, 0.80);
            }
            """

        self.setStyleSheet(base_stylesheet + (dark_overrides if self._is_dark_theme else ""))

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)

        header_widget = QFrame()
        header_widget.setObjectName("HeaderBar")
        header_widget.setFixedHeight(72)
        header_widget.setCursor(Qt.CursorShape.SizeAllCursor)

        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(18, 12, 12, 12)
        header_layout.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel("WhisperOSS")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Voice control center")
        subtitle.setObjectName("Subtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_layout.addLayout(title_col)
        header_layout.addStretch()

        self.status_label = QLabel("Starting")
        self.status_label.setObjectName("StatusBadge")
        self.status_label.setProperty("state", "neutral")
        header_layout.addWidget(self.status_label)

        min_btn = QPushButton("-")
        min_btn.setObjectName("TitleBtn")
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.clicked.connect(self.showMinimized)
        header_layout.addWidget(min_btn)

        close_btn = QPushButton("x")
        close_btn.setObjectName("CloseBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        self._header_widget = header_widget
        header_widget.installEventFilter(self)
        root.addWidget(header_widget)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        root.addLayout(content_layout, 1)

        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(14)

        self.hero_card = GlassPanel()
        self.hero_card.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(8)

        self.record_headline = QLabel("Ready to capture")
        self.record_headline.setObjectName("HeroTitle")
        hero_layout.addWidget(self.record_headline)

        self.record_subtitle = QLabel("Hold Ctrl + Win anywhere to dictate into the active app.")
        self.record_subtitle.setObjectName("MutedText")
        self.record_subtitle.setWordWrap(True)
        hero_layout.addWidget(self.record_subtitle)

        hotkey_note = QLabel("Quick answer mode: hold Win + Ctrl.")
        hotkey_note.setObjectName("MutedText")
        hero_layout.addWidget(hotkey_note)

        hero_layout.addStretch()

        left_layout.addWidget(self.hero_card)

        self.stats_row = QWidget()
        stats_layout = QHBoxLayout(self.stats_row)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)

        capture_card, self.capture_stat_value = self._create_stat_card("Capture", "Standby")
        pipeline_card, self.pipeline_stat_value = self._create_stat_card("Pipeline", "Raw Whisper")
        output_card, self.output_stat_value = self._create_stat_card("Output", "Direct paste")

        stats_layout.addWidget(capture_card)
        stats_layout.addWidget(pipeline_card)
        stats_layout.addWidget(output_card)
        left_layout.addWidget(self.stats_row)

        self.connection_card = GlassPanel()
        self.connection_card.setObjectName("SettingsCard")
        connection_layout = QVBoxLayout(self.connection_card)
        connection_layout.setContentsMargins(18, 18, 18, 18)
        connection_layout.setSpacing(12)

        connection_title = QLabel("Session Configuration")
        connection_title.setObjectName("CardTitle")
        connection_layout.addWidget(connection_title)

        connection_caption = QLabel("Connection")
        connection_caption.setObjectName("SectionCaption")
        connection_layout.addWidget(connection_caption)

        connection_layout.addWidget(QLabel("Groq API Key"))
        api_row = QHBoxLayout()
        api_row.setSpacing(8)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("gsk_...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setText(self.config.get("api_key", ""))
        api_row.addWidget(self.api_key_input, 1)

        self.api_key_toggle_btn = QPushButton("Show")
        self.api_key_toggle_btn.setObjectName("SoftButton")
        self.api_key_toggle_btn.setFixedWidth(76)
        self.api_key_toggle_btn.clicked.connect(self.on_api_key_toggle_visibility)
        api_row.addWidget(self.api_key_toggle_btn)

        connection_layout.addLayout(api_row)

        api_actions = QHBoxLayout()
        api_actions.setSpacing(8)

        self.api_key_save_btn = QPushButton("Validate")
        self.api_key_save_btn.setObjectName("PrimaryAction")
        self.api_key_save_btn.clicked.connect(self.on_api_key_save_clicked)
        api_actions.addWidget(self.api_key_save_btn, 1)

        self.api_key_commit_btn = QPushButton("Save")
        self.api_key_commit_btn.setObjectName("PrimaryAction")
        self.api_key_commit_btn.clicked.connect(self.on_api_key_save_clicked)
        api_actions.addWidget(self.api_key_commit_btn, 1)

        connection_layout.addLayout(api_actions)

        self.api_key_hint = QLabel("Stored locally on this device.")
        self.api_key_hint.setObjectName("ApiHint")
        self.api_key_hint.setProperty("state", "neutral")
        self.api_key_hint.setWordWrap(True)
        connection_layout.addWidget(self.api_key_hint)

        left_layout.addWidget(self.connection_card)
        left_layout.addStretch()

        self.settings_card = GlassPanel()
        self.settings_card.setObjectName("SettingsCard")
        settings_layout = QVBoxLayout(self.settings_card)
        settings_layout.setContentsMargins(18, 18, 18, 18)
        settings_layout.setSpacing(12)

        settings_title = QLabel("Audio & Pipeline")
        settings_title.setObjectName("CardTitle")
        settings_layout.addWidget(settings_title)

        input_caption = QLabel("Audio")
        input_caption.setObjectName("SectionCaption")
        settings_layout.addWidget(input_caption)

        settings_layout.addWidget(QLabel("Microphone"))
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        settings_layout.addWidget(self.device_combo)

        divider_1 = QFrame()
        divider_1.setObjectName("Divider")
        settings_layout.addWidget(divider_1)

        ai_caption = QLabel("AI Pipeline")
        ai_caption.setObjectName("SectionCaption")
        settings_layout.addWidget(ai_caption)

        formatter_row = QHBoxLayout()
        formatter_label = QLabel("AI Formatting")
        self.format_toggle = AnimatedToggle()
        self.format_toggle.setChecked(self.config.get("use_formatter", False))
        self.format_toggle.stateChanged.connect(self.on_toggle_changed)
        formatter_row.addWidget(formatter_label)
        formatter_row.addStretch()
        formatter_row.addWidget(self.format_toggle)
        settings_layout.addLayout(formatter_row)

        self.model_label = QLabel("Formatter Model")
        settings_layout.addWidget(self.model_label)
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        settings_layout.addWidget(self.model_combo)

        divider_2 = QFrame()
        divider_2.setObjectName("Divider")
        settings_layout.addWidget(divider_2)

        output_caption = QLabel("Output")
        output_caption.setObjectName("SectionCaption")
        settings_layout.addWidget(output_caption)

        translation_row = QHBoxLayout()
        translation_label = QLabel("Translation")
        self.translation_toggle = AnimatedToggle()
        self.translation_toggle.setChecked(self.config.get("translation_enabled", False))
        self.translation_toggle.stateChanged.connect(self.on_translate_toggle_changed)
        translation_row.addWidget(translation_label)
        translation_row.addStretch()
        translation_row.addWidget(self.translation_toggle)
        settings_layout.addLayout(translation_row)

        self.language_label = QLabel("Target Language")
        settings_layout.addWidget(self.language_label)

        self.language_input = QComboBox()
        self.language_input.setEditable(True)
        common_languages = [
            "English",
            "Spanish",
            "French",
            "German",
            "Chinese",
            "Japanese",
            "Russian",
            "Portuguese",
            "Italian",
            "Dutch",
            "Korean",
            "Hindi",
            "Arabic",
        ]
        self.language_input.addItems(common_languages)

        current_lang = self.config.get("target_language", "English")
        self.language_input.setCurrentText(current_lang)
        self.language_input.lineEdit().setPlaceholderText("Select or type language")
        self.language_input.currentTextChanged.connect(self.on_language_changed)
        settings_layout.addWidget(self.language_input)

        divider_3 = QFrame()
        divider_3.setObjectName("Divider")
        settings_layout.addWidget(divider_3)

        appearance_caption = QLabel("Appearance")
        appearance_caption.setObjectName("SectionCaption")
        settings_layout.addWidget(appearance_caption)

        settings_layout.addWidget(QLabel("Theme"))
        self.appearance_combo = QComboBox()
        self.appearance_combo.addItems(["Auto", "Dark", "Light"])
        self.appearance_combo.currentTextChanged.connect(self.on_appearance_mode_changed)
        settings_layout.addWidget(self.appearance_combo)

        note = QLabel("Changes are saved immediately and apply to the next recording.")
        note.setObjectName("MutedText")
        note.setWordWrap(True)
        settings_layout.addWidget(note)
        settings_layout.addStretch()

        content_layout.addWidget(left_column, 2)
        content_layout.addWidget(self.settings_card, 1)

    def _create_stat_card(self, title_text, value_text):
        card = GlassPanel()
        card.setObjectName("StatCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title = QLabel(title_text)
        title.setObjectName("StatTitle")
        value = QLabel(value_text)
        value.setObjectName("StatValue")

        layout.addWidget(title)
        layout.addWidget(value)

        return card, value

    def _set_status_badge(self, text, state):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.update()

    def _set_api_key_hint(self, text, state):
        self.api_key_hint.setText(text)
        self.api_key_hint.setProperty("state", state)
        self.api_key_hint.style().unpolish(self.api_key_hint)
        self.api_key_hint.style().polish(self.api_key_hint)
        self.api_key_hint.update()

    def _set_api_key_actions_enabled(self, enabled):
        self.api_key_save_btn.setEnabled(enabled)
        self.api_key_commit_btn.setEnabled(enabled)

    def _refresh_pipeline_summary(self):
        use_formatter = self.format_toggle.isChecked()
        use_translation = self.translation_toggle.isChecked() and self.translation_toggle.isEnabled()

        if not use_formatter:
            pipeline_text = "Raw Whisper"
            output_text = "Direct paste"
        elif use_translation:
            pipeline_text = "Format + Translate"
            lang = self.language_input.currentText().strip() or "Target language"
            output_text = f"{lang} output"
        else:
            pipeline_text = "Format only"
            output_text = "Polished text"

        self.pipeline_stat_value.setText(pipeline_text)
        self.output_stat_value.setText(output_text)

    def _init_ui_state(self):
        """Initialize UI state based on config."""
        self._appearance_mode = self._normalize_appearance_mode(self.config.get("appearance_mode", "auto"))
        self._is_dark_theme = self._resolve_dark_theme()
        self._setup_styling()

        appearance_labels = {"auto": "Auto", "dark": "Dark", "light": "Light"}
        self.appearance_combo.blockSignals(True)
        self.appearance_combo.setCurrentText(appearance_labels[self._appearance_mode])
        self.appearance_combo.blockSignals(False)

        use_formatter = self.config.get("use_formatter", False)
        self.format_toggle.setChecked(use_formatter)
        self.model_combo.setEnabled(use_formatter)
        self.model_label.setEnabled(use_formatter)

        self.translation_toggle.setEnabled(use_formatter)
        translation_enabled = self.config.get("translation_enabled", False) and use_formatter
        self.translation_toggle.setChecked(translation_enabled)
        self.language_input.setEnabled(translation_enabled)
        self.language_label.setEnabled(translation_enabled)

        self._refresh_pipeline_summary()
        self._refresh_theme_widgets()

    # Frameless window dragging / resizing
    _RESIZE_LEFT = 0x1
    _RESIZE_RIGHT = 0x2
    _RESIZE_TOP = 0x4
    _RESIZE_BOTTOM = 0x8

    def _resize_edges_at(self, pos):
        x = pos.x()
        y = pos.y()
        w = self.width()
        h = self.height()
        m = self._resize_margin

        edges = 0
        if x <= m:
            edges |= self._RESIZE_LEFT
        elif x >= w - m:
            edges |= self._RESIZE_RIGHT

        if y <= m:
            edges |= self._RESIZE_TOP
        elif y >= h - m:
            edges |= self._RESIZE_BOTTOM

        return edges

    def _cursor_for_edges(self, edges):
        diagonal_left = self._RESIZE_LEFT | self._RESIZE_TOP
        diagonal_right = self._RESIZE_RIGHT | self._RESIZE_BOTTOM
        diagonal_other_left = self._RESIZE_LEFT | self._RESIZE_BOTTOM
        diagonal_other_right = self._RESIZE_RIGHT | self._RESIZE_TOP

        if edges in (diagonal_left, diagonal_right):
            return Qt.CursorShape.SizeFDiagCursor
        if edges in (diagonal_other_left, diagonal_other_right):
            return Qt.CursorShape.SizeBDiagCursor
        if edges & (self._RESIZE_LEFT | self._RESIZE_RIGHT):
            return Qt.CursorShape.SizeHorCursor
        if edges & (self._RESIZE_TOP | self._RESIZE_BOTTOM):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def _apply_resize(self, global_pos):
        delta = global_pos - self._press_global_pos
        geom = self._press_geometry

        min_w = self.minimumWidth()
        min_h = self.minimumHeight()

        left = geom.left()
        right = geom.right()
        top = geom.top()
        bottom = geom.bottom()

        if self._resize_edges & self._RESIZE_LEFT:
            left = min(left + delta.x(), right - min_w + 1)
        if self._resize_edges & self._RESIZE_RIGHT:
            right = max(right + delta.x(), left + min_w - 1)
        if self._resize_edges & self._RESIZE_TOP:
            top = min(top + delta.y(), bottom - min_h + 1)
        if self._resize_edges & self._RESIZE_BOTTOM:
            bottom = max(bottom + delta.y(), top + min_h - 1)

        self.setGeometry(left, top, right - left + 1, bottom - top + 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._resize_edges_at(event.position().toPoint())
            if edges:
                self._resizing = True
                self._resize_edges = edges
                self._press_global_pos = event.globalPosition().toPoint()
                self._press_geometry = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._resizing = False
            self._resize_edges = 0
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            self._apply_resize(event.globalPosition().toPoint())
            event.accept()
            return

        if self._dragging:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()
            event.accept()
            return

        edges = self._resize_edges_at(event.position().toPoint())
        self.setCursor(self._cursor_for_edges(edges))
        super().mouseMoveEvent(event)

    def eventFilter(self, obj, event):
        if obj == getattr(self, "_header_widget", None):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                edges = self._resize_edges_at(event.position().toPoint())
                if edges:
                    return False
                self.oldPos = event.globalPosition().toPoint()
                self._dragging = True
                return True

            if event.type() == QEvent.Type.MouseButtonRelease:
                self._dragging = False
                return True

            if event.type() == QEvent.Type.MouseMove and self._dragging:
                delta = event.globalPosition().toPoint() - self.oldPos
                self.move(self.x() + delta.x(), self.y() + delta.y())
                self.oldPos = event.globalPosition().toPoint()
                return True

        return super().eventFilter(obj, event)


    def showEvent(self, event):
        super().showEvent(event)
        if self.layout() is not None:
            self.layout().activate()
        QTimer.singleShot(0, self.update)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and self._appearance_mode == "auto":
            refreshed_dark_mode = self._resolve_dark_theme()
            if refreshed_dark_mode != self._is_dark_theme:
                self._is_dark_theme = refreshed_dark_mode
                self._setup_styling()
                self._refresh_theme_widgets()
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._is_dark_theme:
            if self._blur_active:
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0.0, QColor(2, 6, 23, 178))
                gradient.setColorAt(1.0, QColor(15, 23, 42, 178))
                border_color = QColor(45, 212, 191, 136)
            else:
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0.0, QColor(2, 6, 23, 246))
                gradient.setColorAt(1.0, QColor(15, 23, 42, 246))
                border_color = QColor(30, 41, 59, 180)
        else:
            if self._blur_active:
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0.0, QColor(238, 242, 255, 168))
                gradient.setColorAt(1.0, QColor(226, 232, 240, 168))
                border_color = QColor(255, 255, 255, 110)
            else:
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0.0, QColor(241, 245, 249, 246))
                gradient.setColorAt(1.0, QColor(226, 232, 240, 246))
                border_color = QColor(148, 163, 184, 120)

        painter.setBrush(QBrush(gradient))
        shell_rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(shell_rect, 24, 24)

        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(shell_rect, 24, 24)

    # Event handlers
    def set_recording_state(self, is_recording):
        self.is_recording = is_recording
        if is_recording:
            self.record_headline.setText("Listening...")
            self.record_subtitle.setText("Release the hotkey to transcribe and paste into the active app.")
            self.capture_stat_value.setText("Recording")
        else:
            self.record_headline.setText("Ready to capture")
            self.record_subtitle.setText("Hold Ctrl + Win anywhere to dictate into the active app.")
            self.capture_stat_value.setText("Standby")

    def on_device_changed(self, index):
        if index < 0:
            return

        device_id = self.device_combo.itemData(index)
        self.config.set("input_device_index", device_id)
        self.config.save()
        self.config_changed.emit("input_device_index", device_id)

    def on_toggle_changed(self, state):
        enabled = state == int(Qt.CheckState.Checked.value)
        self.config.set("use_formatter", enabled)
        self.config.save()

        self.model_combo.setEnabled(enabled)
        self.model_label.setEnabled(enabled)
        self.translation_toggle.setEnabled(enabled)

        # Translation depends on formatter.
        if not enabled:
            self.translation_toggle.blockSignals(True)
            self.translation_toggle.setChecked(False)
            self.translation_toggle.blockSignals(False)
            self.config.set("translation_enabled", False)
            self.config.save()
            self.language_input.setEnabled(False)
            self.language_label.setEnabled(False)
        else:
            trans_enabled = self.translation_toggle.isChecked()
            self.language_input.setEnabled(trans_enabled)
            self.language_label.setEnabled(trans_enabled)

        self._refresh_pipeline_summary()

    def on_translate_toggle_changed(self, state):
        enabled = state == int(Qt.CheckState.Checked.value)
        self.config.set("translation_enabled", enabled)
        self.config.save()
        self.language_input.setEnabled(enabled)
        self.language_label.setEnabled(enabled)
        self._refresh_pipeline_summary()

    def on_language_changed(self, text):
        self.config.set("target_language", text)
        self.config.save()
        self._refresh_pipeline_summary()

    def on_model_changed(self, text):
        if text:
            self.config.set("formatter_model", text)
            self.config.save()

    def on_appearance_mode_changed(self, text):
        selected_mode = self._normalize_appearance_mode(text)
        if selected_mode == self._appearance_mode:
            return

        self._appearance_mode = selected_mode
        self.config.set("appearance_mode", selected_mode)
        self.config.save()

        self._is_dark_theme = self._resolve_dark_theme()
        self._setup_styling()
        self._refresh_theme_widgets()
        self.update()

    def on_api_key_toggle_visibility(self):
        showing = self.api_key_input.echoMode() == QLineEdit.EchoMode.Normal
        if showing:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.api_key_toggle_btn.setText("Show")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.api_key_toggle_btn.setText("Hide")

    def on_api_key_save_clicked(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            self._set_api_key_hint("Enter a valid Groq API key.", "error")
            return

        self._set_api_key_actions_enabled(False)
        self.api_key_save_btn.setText("Validating...")
        self.api_key_commit_btn.setText("Save")
        self._set_api_key_hint("Validating key with Groq...", "neutral")
        self.config_changed.emit("api_key", api_key)

    def set_api_key_validation_result(self, valid, message):
        self._set_api_key_actions_enabled(True)
        self.api_key_save_btn.setText("Validate")
        self.api_key_commit_btn.setText("Save")
        self._set_api_key_hint(message, "ok" if valid else "error")

    def update_log(self, text):
        display = text if len(text) <= 42 else text[:39] + "..."

        normalized = text.lower()
        if normalized.startswith("error"):
            state = "error"
        elif "connected" in normalized:
            state = "ok"
        else:
            state = "neutral"

        self._set_status_badge(display, state)

    def update_visualizer_level(self, level):
        # Kept for controller compatibility. The in-window mic tester was removed.
        _ = level

    def set_device_list(self, devices):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()

        current_dev = self.config.get("input_device_index")
        for index, (device_id, name) in enumerate(devices):
            self.device_combo.addItem(name, device_id)
            if device_id == current_dev:
                self.device_combo.setCurrentIndex(index)

        self.device_combo.blockSignals(False)

    def set_model_list(self, models):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)

        current_model = self.config.get("formatter_model")
        if current_model in models:
            self.model_combo.setCurrentText(current_model)

        self.model_combo.blockSignals(False)

    def _set_connected_status(self, text):
        self._set_status_badge(text, "ok")

    def _set_error_status(self, text):
        self._set_status_badge(text, "error")
