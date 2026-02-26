from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QPropertyAnimation,
    QEasingCurve,
    QTimer,
    QPoint,
    QSize,
    pyqtProperty,
    QEvent,
)
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QBrush,
    QPen,
    QLinearGradient,
    QRadialGradient,
    QFont,
    QPalette,
    QPainterPath,
    QRegion,
)
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
    QTabWidget,
    QScrollArea,
    QGraphicsOpacityEffect,
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
                track_color = QColor("#3b82f6") if dark_theme else QColor("#0ea5e9")
            else:
                track_color = QColor("#2b3b54") if dark_theme else QColor("#cbd5e1")
        else:
            track_color = QColor("#1a2536") if dark_theme else QColor("#e2e8f0")

        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)

        handle_color = QColor("#dbeafe") if dark_theme else QColor("#ffffff")
        painter.setBrush(QBrush(handle_color))
        painter.drawEllipse(int(self._handle_position), 4, 20, 20)


class PulsingRecordButton(QPushButton):
    """Primary CTA button with subtle pulse while recording."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("START")
        self.setFixedSize(104, 104)
        self.setCheckable(True)

        self._pulse_opacity = 0.0
        self._pulse_scale = 1.0
        self._pulse_phase = 0.0
        self._is_recording = False

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_timer.start(30)

    def setRecording(self, recording):
        self._is_recording = recording
        self.setText("STOP" if recording else "START")
        self.update()

    def _update_pulse(self):
        if self._is_recording:
            import math

            self._pulse_phase += 0.11
            self._pulse_opacity = 0.24 + 0.24 * math.sin(self._pulse_phase)
            self._pulse_scale = 1.0 + 0.08 * math.sin(self._pulse_phase)
        else:
            self._pulse_opacity = max(0.0, self._pulse_opacity - 0.05)
            self._pulse_scale = 1.0 + (self._pulse_scale - 1.0) * 0.86
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() // 2, self.height() // 2
        radius = 46

        if self._pulse_opacity > 0.01:
            glow_radius = radius * self._pulse_scale * 1.5
            glow = QRadialGradient(cx, cy, glow_radius)
            glow.setColorAt(0.0, QColor(14, 165, 233, int(220 * self._pulse_opacity)))
            glow.setColorAt(0.6, QColor(2, 132, 199, int(90 * self._pulse_opacity)))
            glow.setColorAt(1.0, QColor(2, 132, 199, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(
                int(cx - glow_radius),
                int(cy - glow_radius),
                int(glow_radius * 2),
                int(glow_radius * 2),
            )

        gradient = QRadialGradient(cx - 6, cy - 8, radius)
        if self._is_recording:
            gradient.setColorAt(0.0, QColor("#0284c7"))
            gradient.setColorAt(0.7, QColor("#0369a1"))
            gradient.setColorAt(1.0, QColor("#075985"))
        else:
            gradient.setColorAt(0.0, QColor("#1d4ed8"))
            gradient.setColorAt(0.7, QColor("#1e40af"))
            gradient.setColorAt(1.0, QColor("#1e3a8a"))

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor("#ffffff40"), 2))
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        highlight = QRadialGradient(cx - 14, cy - 18, radius * 0.7)
        highlight.setColorAt(0.0, QColor(255, 255, 255, 84))
        highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(highlight))
        painter.drawEllipse(cx - radius + 8, cy - radius + 6, radius + 8, radius)

        painter.setPen(QPen(QColor("#f8fafc")))
        painter.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.DemiBold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())


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
                top = QColor(18, 29, 47, 248)
                bottom = QColor(12, 20, 34, 246)
                border = QColor(70, 108, 160, 86)
            elif card_name == "SettingsCard":
                top = QColor(15, 24, 40, 248)
                bottom = QColor(10, 17, 30, 246)
                border = QColor(64, 96, 140, 82)
            elif card_name == "StatCard":
                top = QColor(22, 34, 53, 246)
                bottom = QColor(14, 24, 39, 244)
                border = QColor(68, 102, 150, 84)
            else:
                top = QColor(15, 24, 40, 246)
                bottom = QColor(10, 18, 31, 244)
                border = QColor(64, 96, 140, 80)
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
        self._intro_animations = []
        self._dragging = False
        self.oldPos = self.pos()
        self._initial_layout_applied = False
        self._appearance_mode = self._normalize_appearance_mode(self.config.get("appearance_mode", "auto"))
        self._animation_fps = self._normalize_animation_fps(self.config.get("animation_fps", 100))
        self._is_dark_theme = self._resolve_dark_theme()

        # Frameless layout keeps this feeling like a polished desktop app shell.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)

        self._apply_blur_effect()
        self._setup_styling()

        self.is_recording = False
        self.setup_ui()
        self._init_ui_state()
        self._play_intro_animation()

    def _apply_blur_effect(self):
        """Apply Windows acrylic blur when available."""
        try:
            from src.window_effects import WindowEffect

            self._window_effect = WindowEffect()

            def apply_and_track():
                try:
                    self._blur_active = self._window_effect.set_acrylic(self.winId())
                    self._window_effect.set_rounded_corners(self.winId())
                    if self._blur_active:
                        self.update()
                except RuntimeError:
                    # Widget was already destroyed before the timer fired (e.g. in tests).
                    pass

            QTimer.singleShot(100, apply_and_track)
        except ImportError:
            self._blur_active = False

    def _normalize_appearance_mode(self, mode):
        normalized = str(mode or "auto").strip().lower()
        return normalized if normalized in {"auto", "dark", "light"} else "auto"

    def _normalize_animation_fps(self, value):
        try:
            fps = int(value)
        except (TypeError, ValueError):
            fps = 100
        return max(30, min(240, fps))

    def _normalize_proxy_thinking_level(self, value):
        normalized = str(value or "high").strip().lower()
        return normalized if normalized in {"high", "medium", "low", "none"} else "high"

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

            QTabWidget#SettingsTabs::pane {
                border: none;
                background: transparent;
                margin-top: 4px;
            }

            QTabWidget#SettingsTabs QTabBar::tab {
                border: 1px solid rgba(148, 163, 184, 0.56);
                border-radius: 10px;
                padding: 6px 12px;
                margin-right: 6px;
                background: rgba(241, 245, 249, 0.78);
                color: #334155;
                font-weight: 600;
            }

            QTabWidget#SettingsTabs QTabBar::tab:selected {
                border: 1px solid #0ea5e9;
                background: rgba(224, 242, 254, 0.92);
                color: #0f172a;
            }

            QTabWidget#SettingsTabs QTabBar::tab:hover:!selected {
                border: 1px solid #94a3b8;
                background: rgba(226, 232, 240, 0.88);
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

            QLabel#SaveFeedback {
                color: #0f766e;
                font-size: 12px;
                font-weight: 700;
            }

            QLabel#SaveFeedback[state='error'] {
                color: #b91c1c;
            }

            QFrame#ProxyHelp {
                border: 1px solid rgba(248, 113, 113, 0.34);
                border-radius: 10px;
                background: rgba(254, 226, 226, 0.46);
            }

            QScrollArea#ProxyHelpScroll {
                border: none;
                background: transparent;
            }

            QFrame#Divider {
                min-height: 1px;
                max-height: 1px;
                background: rgba(148, 163, 184, 0.34);
            }
            """

        dark_overrides = """
            QWidget {
                color: #dde7f6;
            }

            QFrame#HeaderBar {
                border: 1px solid rgba(83, 119, 166, 0.62);
                background: rgba(11, 18, 31, 0.92);
            }

            QLabel#WindowTitle {
                color: #f2f7ff;
            }

            QLabel#Subtitle {
                color: #9fb2cf;
            }

            QLabel#StatusBadge {
                background: #131f33;
                color: #ccdaee;
                border: 1px solid #314b72;
            }

            QLabel#StatusBadge[state='ok'] {
                background: #0f2a23;
                border: 1px solid #2f8f75;
                color: #b8f3df;
            }

            QLabel#StatusBadge[state='error'] {
                background: #3c151e;
                border: 1px solid #bc4f67;
                color: #ffd5df;
            }

            QLabel#StatusBadge[state='active'] {
                background: #143154;
                border: 1px solid #4d8ad0;
                color: #d3e9ff;
            }

            QPushButton#TitleBtn,
            QPushButton#CloseBtn {
                border: 1px solid #35507a;
                background: #111c2f;
                color: #cfdcf0;
            }

            QPushButton#TitleBtn:hover {
                background: #182741;
                border: 1px solid #4f74ac;
            }

            QPushButton#CloseBtn:hover {
                background: #4f1d29;
                border: 1px solid #ca5f78;
                color: #ffe4ea;
            }

            QLabel#HeroTitle,
            QLabel#CardTitle,
            QLabel#StatValue {
                color: #edf4ff;
            }

            QLabel#MutedText {
                color: #9fb1cd;
            }

            QLabel#SectionCaption,
            QLabel#StatTitle {
                color: #8fc4ff;
            }

            QTabWidget#SettingsTabs::pane {
                border: none;
                background: transparent;
                margin-top: 4px;
            }

            QTabWidget#SettingsTabs QTabBar::tab {
                border: 1px solid #35507a;
                border-radius: 10px;
                background: rgba(17, 28, 47, 0.82);
                color: #bcd0ed;
            }

            QTabWidget#SettingsTabs QTabBar::tab:selected {
                border: 1px solid #4d8ad0;
                background: rgba(24, 44, 72, 0.96);
                color: #edf4ff;
            }

            QTabWidget#SettingsTabs QTabBar::tab:hover:!selected {
                border: 1px solid #4d8ad0;
                background: rgba(27, 45, 72, 0.90);
            }

            QComboBox {
                border: 1px solid #35507a;
                background: rgba(10, 16, 28, 0.94);
                color: #e7effc;
            }

            QComboBox:hover {
                border: 1px solid #4d8ad0;
            }

            QComboBox:focus {
                border: 1px solid #74afff;
            }

            QComboBox::down-arrow {
                border-top: 6px solid #a8bbd8;
            }

            QComboBox QAbstractItemView {
                border: 1px solid #35507a;
                background: #0a1221;
                selection-background-color: #2f67bc;
                selection-color: #f2f7ff;
                color: #e5eefc;
            }

            QLineEdit {
                border: 1px solid #35507a;
                background: rgba(10, 16, 28, 0.94);
                color: #e7effc;
            }

            QLineEdit:focus {
                border: 1px solid #74afff;
            }

            QPushButton#SoftButton {
                border: 1px solid #35507a;
                background: #152338;
                color: #cfddf2;
            }

            QPushButton#SoftButton:hover {
                border: 1px solid #4d8ad0;
                background: #1b2d48;
            }

            QPushButton#PrimaryAction {
                border: 1px solid #3f73c8;
                background: #2c63ba;
                color: #f4f8ff;
            }

            QPushButton#PrimaryAction:hover {
                border: 1px solid #5a97f2;
                background: #3976d7;
            }

            QPushButton#PrimaryAction:disabled {
                border: 1px solid #2f476c;
                background: #1a2639;
                color: #7487a5;
            }

            QLabel#ApiHint {
                color: #aac6ee;
            }

            QLabel#ApiHint[state='ok'] {
                color: #a6efd4;
            }

            QLabel#ApiHint[state='error'] {
                color: #ffc3d2;
            }

            QLabel#SaveFeedback {
                color: #a6efd4;
            }

            QLabel#SaveFeedback[state='error'] {
                color: #ffc3d2;
            }

            QFrame#ProxyHelp {
                border: 1px solid rgba(188, 79, 103, 0.64);
                border-radius: 10px;
                background: rgba(60, 21, 30, 0.68);
            }

            QScrollArea#ProxyHelpScroll {
                border: none;
                background: transparent;
            }

            QFrame#Divider {
                background: rgba(57, 83, 120, 0.88);
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

        self.settings_tabs = QTabWidget()
        self.settings_tabs.setObjectName("SettingsTabs")
        self.settings_tabs.setDocumentMode(True)
        self.settings_tabs.tabBar().setExpanding(True)
        self.settings_tabs.tabBar().setUsesScrollButtons(False)
        self.settings_tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.settings_tabs.tabBar().setDrawBase(False)
        settings_layout.addWidget(self.settings_tabs, 1)

        save_action_row = QHBoxLayout()
        save_action_row.setContentsMargins(0, 0, 0, 0)
        save_action_row.setSpacing(8)
        save_action_row.addStretch()

        self.force_save_feedback = QLabel("✓ Saved")
        self.force_save_feedback.setObjectName("SaveFeedback")
        self.force_save_feedback.setProperty("state", "ok")
        self.force_save_feedback.setVisible(False)
        self.force_save_feedback_effect = QGraphicsOpacityEffect(self.force_save_feedback)
        self.force_save_feedback_effect.setOpacity(0.0)
        self.force_save_feedback.setGraphicsEffect(self.force_save_feedback_effect)
        save_action_row.addWidget(self.force_save_feedback)

        self.force_save_btn = QPushButton("Save")
        self.force_save_btn.setObjectName("PrimaryAction")
        self.force_save_btn.setToolTip("Force save settings and re-apply runtime configuration.")
        self.force_save_btn.setMinimumWidth(120)
        self.force_save_btn.clicked.connect(self.on_force_save_clicked)
        save_action_row.addWidget(self.force_save_btn)

        self.force_save_fade_in = QPropertyAnimation(self.force_save_feedback_effect, b"opacity", self)
        self.force_save_fade_in.setDuration(130)
        self.force_save_fade_in.setStartValue(0.0)
        self.force_save_fade_in.setEndValue(1.0)
        self.force_save_fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.force_save_fade_out = QPropertyAnimation(self.force_save_feedback_effect, b"opacity", self)
        self.force_save_fade_out.setDuration(260)
        self.force_save_fade_out.setStartValue(1.0)
        self.force_save_fade_out.setEndValue(0.0)
        self.force_save_fade_out.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.force_save_fade_out.finished.connect(self._hide_force_save_feedback)

        self.force_save_hide_timer = QTimer(self)
        self.force_save_hide_timer.setSingleShot(True)
        self.force_save_hide_timer.timeout.connect(self._fade_out_force_save_feedback)

        self._force_save_in_progress = False
        self._force_save_loading_step = 0
        self.force_save_loading_timer = QTimer(self)
        self.force_save_loading_timer.setInterval(170)
        self.force_save_loading_timer.timeout.connect(self._tick_force_save_loading)

        settings_layout.addLayout(save_action_row)

        # Pipeline tab
        pipeline_tab = QWidget()
        pipeline_layout = QVBoxLayout(pipeline_tab)
        pipeline_layout.setContentsMargins(8, 10, 8, 8)
        pipeline_layout.setSpacing(12)

        input_caption = QLabel("Audio")
        input_caption.setObjectName("SectionCaption")
        pipeline_layout.addWidget(input_caption)

        pipeline_layout.addWidget(QLabel("Microphone"))
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        pipeline_layout.addWidget(self.device_combo)

        divider_1 = QFrame()
        divider_1.setObjectName("Divider")
        pipeline_layout.addWidget(divider_1)

        ai_caption = QLabel("AI Pipeline")
        ai_caption.setObjectName("SectionCaption")
        pipeline_layout.addWidget(ai_caption)

        formatter_row = QHBoxLayout()
        formatter_label = QLabel("AI Formatting")
        self.format_toggle = AnimatedToggle()
        self.format_toggle.setChecked(self.config.get("use_formatter", False))
        self.format_toggle.stateChanged.connect(self.on_toggle_changed)
        formatter_row.addWidget(formatter_label)
        formatter_row.addStretch()
        formatter_row.addWidget(self.format_toggle)
        pipeline_layout.addLayout(formatter_row)

        self.model_label = QLabel("Formatter Model")
        pipeline_layout.addWidget(self.model_label)
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        pipeline_layout.addWidget(self.model_combo)
        pipeline_layout.addStretch()

        self.settings_tabs.addTab(pipeline_tab, "Pipeline")

        # Output tab
        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)
        output_layout.setContentsMargins(8, 10, 8, 8)
        output_layout.setSpacing(12)

        output_caption = QLabel("Output")
        output_caption.setObjectName("SectionCaption")
        output_layout.addWidget(output_caption)

        translation_row = QHBoxLayout()
        translation_label = QLabel("Translation")
        self.translation_toggle = AnimatedToggle()
        self.translation_toggle.setChecked(self.config.get("translation_enabled", False))
        self.translation_toggle.stateChanged.connect(self.on_translate_toggle_changed)
        translation_row.addWidget(translation_label)
        translation_row.addStretch()
        translation_row.addWidget(self.translation_toggle)
        output_layout.addLayout(translation_row)

        self.language_label = QLabel("Target Language")
        output_layout.addWidget(self.language_label)

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
        output_layout.addWidget(self.language_input)
        output_layout.addStretch()

        self.settings_tabs.addTab(output_tab, "Output")

        # Advanced tab (scrollable so it never clips controls)
        advanced_tab = QScrollArea()
        advanced_tab.setObjectName("AdvancedTabScroll")
        advanced_tab.setWidgetResizable(True)
        advanced_tab.setFrameShape(QFrame.Shape.NoFrame)
        advanced_tab.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        advanced_page = QWidget()
        advanced_layout = QVBoxLayout(advanced_page)
        advanced_layout.setContentsMargins(8, 10, 8, 8)
        advanced_layout.setSpacing(12)

        proxy_row = QHBoxLayout()
        self.proxy_search_label = QLabel("Antigravity Proxy (Search)")
        self.proxy_search_toggle = AnimatedToggle()
        self.proxy_search_toggle.setChecked(
            bool(self.config.get("use_antigravity_proxy_search", False))
        )
        self.proxy_search_toggle.stateChanged.connect(self.on_proxy_search_toggle_changed)
        proxy_row.addWidget(self.proxy_search_label)
        proxy_row.addStretch()
        proxy_row.addWidget(self.proxy_search_toggle)
        advanced_layout.addLayout(proxy_row)

        # Collapsible instructions panel with animation + internal scrolling.
        self.proxy_setup_container = QFrame()
        self.proxy_setup_container.setObjectName("ProxyHelp")
        self.proxy_setup_container.setMaximumHeight(0)
        self.proxy_setup_container.setMinimumHeight(0)
        proxy_setup_outer = QVBoxLayout(self.proxy_setup_container)
        proxy_setup_outer.setContentsMargins(8, 8, 8, 8)
        proxy_setup_outer.setSpacing(0)

        self.proxy_setup_scroll = QScrollArea()
        self.proxy_setup_scroll.setObjectName("ProxyHelpScroll")
        self.proxy_setup_scroll.setWidgetResizable(True)
        self.proxy_setup_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.proxy_setup_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.proxy_setup_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        proxy_setup_content = QWidget()
        proxy_setup_content_layout = QVBoxLayout(proxy_setup_content)
        proxy_setup_content_layout.setContentsMargins(0, 0, 0, 0)
        proxy_setup_content_layout.setSpacing(0)
        self.proxy_setup_hint = QLabel(
            "Advanced mode. Not out-of-the-box.\n"
            "Setup steps:\n"
            "1) Install and run Antigravity Manager (proxy) locally.\n"
            "2) Start the proxy and keep it reachable (default: http://127.0.0.1:8045).\n"
            "3) Enable MCP Web Search in Antigravity Manager.\n"
            "4) Paste the proxy API key below and choose search-capable models."
        )
        self.proxy_setup_hint.setObjectName("ApiHint")
        self.proxy_setup_hint.setProperty("state", "error")
        self.proxy_setup_hint.setWordWrap(True)
        proxy_setup_content_layout.addWidget(self.proxy_setup_hint)
        self.proxy_setup_scroll.setWidget(proxy_setup_content)
        proxy_setup_outer.addWidget(self.proxy_setup_scroll)
        advanced_layout.addWidget(self.proxy_setup_container)

        self.proxy_setup_anim = QPropertyAnimation(self.proxy_setup_container, b"maximumHeight", self)
        self.proxy_setup_anim.setDuration(220)
        self.proxy_setup_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.proxy_url_label = QLabel("Proxy Base URL")
        advanced_layout.addWidget(self.proxy_url_label)
        self.proxy_url_input = QLineEdit()
        self.proxy_url_input.setPlaceholderText("http://127.0.0.1:8045")
        self.proxy_url_input.setText(self.config.get("antigravity_proxy_url", "http://127.0.0.1:8045"))
        self.proxy_url_input.editingFinished.connect(self.on_proxy_url_changed)
        advanced_layout.addWidget(self.proxy_url_input)

        self.proxy_api_key_label = QLabel("Proxy API Key")
        advanced_layout.addWidget(self.proxy_api_key_label)
        proxy_api_row = QHBoxLayout()
        proxy_api_row.setSpacing(8)
        self.proxy_api_key_input = QLineEdit()
        self.proxy_api_key_input.setPlaceholderText("Optional proxy API key")
        self.proxy_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.proxy_api_key_input.setText(self.config.get("antigravity_api_key", ""))
        self.proxy_api_key_input.editingFinished.connect(self.on_proxy_api_key_changed)
        proxy_api_row.addWidget(self.proxy_api_key_input, 1)
        self.proxy_api_key_toggle_btn = QPushButton("Show")
        self.proxy_api_key_toggle_btn.setObjectName("SoftButton")
        self.proxy_api_key_toggle_btn.setFixedWidth(76)
        self.proxy_api_key_toggle_btn.clicked.connect(self.on_proxy_api_key_toggle_visibility)
        proxy_api_row.addWidget(self.proxy_api_key_toggle_btn)
        advanced_layout.addLayout(proxy_api_row)

        self.proxy_model_label = QLabel("Proxy Search Model")
        advanced_layout.addWidget(self.proxy_model_label)
        self.proxy_model_input = QLineEdit()
        self.proxy_model_input.setPlaceholderText("gemini-3-flash")
        self.proxy_model_input.setText(self.config.get("antigravity_search_model", "gemini-3-flash"))
        self.proxy_model_input.editingFinished.connect(self.on_proxy_model_changed)
        advanced_layout.addWidget(self.proxy_model_input)

        self.proxy_fallback_model_label = QLabel("Proxy Fallback Model")
        advanced_layout.addWidget(self.proxy_fallback_model_label)
        self.proxy_fallback_model_input = QLineEdit()
        self.proxy_fallback_model_input.setPlaceholderText("gemini-2.5-flash")
        self.proxy_fallback_model_input.setText(
            self.config.get("antigravity_search_fallback_model", "gemini-2.5-flash")
        )
        self.proxy_fallback_model_input.editingFinished.connect(
            self.on_proxy_fallback_model_changed
        )
        advanced_layout.addWidget(self.proxy_fallback_model_input)

        self.proxy_thinking_label = QLabel("Proxy Thinking Level")
        advanced_layout.addWidget(self.proxy_thinking_label)
        self.proxy_thinking_combo = QComboBox()
        self.proxy_thinking_combo.addItems(["High", "Medium", "Low", "None"])
        thinking_level = self._normalize_proxy_thinking_level(
            self.config.get("antigravity_thinking_level", "high")
        )
        thinking_labels = {
            "high": "High",
            "medium": "Medium",
            "low": "Low",
            "none": "None",
        }
        self.proxy_thinking_combo.setCurrentText(thinking_labels[thinking_level])
        self.proxy_thinking_combo.currentTextChanged.connect(
            self.on_proxy_thinking_level_changed
        )
        advanced_layout.addWidget(self.proxy_thinking_combo)
        advanced_layout.addStretch()

        advanced_tab.setWidget(advanced_page)
        self.settings_tabs.addTab(advanced_tab, "Advanced")

        # Appearance tab
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout(appearance_tab)
        appearance_layout.setContentsMargins(8, 10, 8, 8)
        appearance_layout.setSpacing(12)

        appearance_caption = QLabel("Appearance")
        appearance_caption.setObjectName("SectionCaption")
        appearance_layout.addWidget(appearance_caption)

        appearance_layout.addWidget(QLabel("Theme"))
        self.appearance_combo = QComboBox()
        self.appearance_combo.addItems(["Auto", "Dark", "Light"])
        self.appearance_combo.currentTextChanged.connect(self.on_appearance_mode_changed)
        appearance_layout.addWidget(self.appearance_combo)

        appearance_layout.addWidget(QLabel("Animation FPS"))
        self.animation_fps_combo = QComboBox()
        self.animation_fps_combo.addItems(["60", "75", "90", "100", "120", "144", "165", "240"])
        self.animation_fps_combo.currentTextChanged.connect(self.on_animation_fps_changed)
        appearance_layout.addWidget(self.animation_fps_combo)

        note = QLabel("Changes are saved immediately and apply to the next recording.")
        note.setObjectName("MutedText")
        note.setWordWrap(True)
        appearance_layout.addWidget(note)
        appearance_layout.addStretch()

        self.settings_tabs.addTab(appearance_tab, "Theme")

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

    def _play_intro_animation(self):
        """Stagger card fade-ins so the shell feels intentional and responsive."""
        self._intro_animations.clear()
        targets = [self._header_widget, self.hero_card, self.stats_row, self.connection_card, self.settings_card]

        for index, target in enumerate(targets):
            effect = QGraphicsOpacityEffect(target)
            effect.setOpacity(0.0)
            target.setGraphicsEffect(effect)

            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.setDuration(280)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._intro_animations.append(animation)

            QTimer.singleShot(index * 70, animation.start)

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

    def _show_force_save_feedback(self, text, state):
        self.force_save_hide_timer.stop()
        self.force_save_fade_in.stop()
        self.force_save_fade_out.stop()

        self.force_save_feedback.setText(text)
        self.force_save_feedback.setProperty("state", state)
        self.force_save_feedback.style().unpolish(self.force_save_feedback)
        self.force_save_feedback.style().polish(self.force_save_feedback)
        self.force_save_feedback.setVisible(True)
        self.force_save_feedback_effect.setOpacity(0.0)
        self.force_save_fade_in.start()

        if state == "ok":
            self.force_save_hide_timer.start(1200)

    def _fade_out_force_save_feedback(self):
        self.force_save_fade_out.stop()
        self.force_save_fade_out.start()

    def _hide_force_save_feedback(self):
        self.force_save_feedback.setVisible(False)

    def _tick_force_save_loading(self):
        dots = "." * ((self._force_save_loading_step % 3) + 1)
        self.force_save_btn.setText(f"Saving{dots}")
        self._force_save_loading_step += 1

    def _start_force_save_loading(self):
        self._force_save_in_progress = True
        self._force_save_loading_step = 0
        self.force_save_btn.setEnabled(False)
        self.force_save_btn.setText("Saving...")
        self.force_save_loading_timer.start()

    def _stop_force_save_loading(self):
        self.force_save_loading_timer.stop()
        self.force_save_btn.setEnabled(True)
        self.force_save_btn.setText("Save")
        self._force_save_in_progress = False

    def _persist_force_save_settings(self):
        self.config.set("input_device_index", self.device_combo.currentData())
        self.config.set("use_formatter", self.format_toggle.isChecked())
        self.config.set("formatter_model", self.model_combo.currentText().strip())
        self.config.set(
            "translation_enabled",
            self.translation_toggle.isChecked() and self.translation_toggle.isEnabled(),
        )
        self.config.set("target_language", self.language_input.currentText().strip() or "English")
        self.config.set("appearance_mode", self._appearance_mode)
        self.config.set("animation_fps", self._animation_fps)

        self.config.set("use_antigravity_proxy_search", self.proxy_search_toggle.isChecked())
        self.config.set("antigravity_proxy_url", self.proxy_url_input.text().strip())
        self.config.set("antigravity_api_key", self.proxy_api_key_input.text().strip())
        self.config.set("antigravity_search_model", self.proxy_model_input.text().strip())
        self.config.set(
            "antigravity_search_fallback_model",
            self.proxy_fallback_model_input.text().strip(),
        )
        self.config.set(
            "antigravity_thinking_level",
            self._normalize_proxy_thinking_level(self.proxy_thinking_combo.currentText()),
        )

        return self.config.save()

    def _emit_force_reconfigure(self):
        device_id = self.device_combo.currentData()
        if device_id is not None:
            self.config_changed.emit("input_device_index", device_id)

        self.config_changed.emit("animation_fps", self._animation_fps)

        proxy_enabled = self.proxy_search_toggle.isChecked()
        self.config_changed.emit("use_antigravity_proxy_search", proxy_enabled)
        self.config_changed.emit("antigravity_proxy_url", self.proxy_url_input.text().strip())
        self.config_changed.emit("antigravity_api_key", self.proxy_api_key_input.text().strip())
        self.config_changed.emit("antigravity_search_model", self.proxy_model_input.text().strip())
        self.config_changed.emit(
            "antigravity_search_fallback_model",
            self.proxy_fallback_model_input.text().strip(),
        )
        self.config_changed.emit(
            "antigravity_thinking_level",
            self._normalize_proxy_thinking_level(self.proxy_thinking_combo.currentText()),
        )

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

    def _proxy_help_target_height(self):
        if not hasattr(self, "proxy_setup_scroll"):
            return 0
        hint_height = self.proxy_setup_hint.sizeHint().height()
        # Keep instructions in a compact area; allow scrolling for the full text.
        return min(130, hint_height + 12)

    def _animate_proxy_help(self, show):
        if not hasattr(self, "proxy_setup_anim"):
            return

        start_height = self.proxy_setup_container.maximumHeight()
        end_height = self._proxy_help_target_height() if show else 0
        self.proxy_setup_anim.stop()
        self.proxy_setup_anim.setStartValue(start_height)
        self.proxy_setup_anim.setEndValue(end_height)
        self.proxy_setup_anim.start()

    def _set_proxy_settings_enabled(self, enabled, animate=False):
        self.proxy_url_label.setEnabled(enabled)
        self.proxy_url_input.setEnabled(enabled)
        self.proxy_api_key_label.setEnabled(enabled)
        self.proxy_api_key_input.setEnabled(enabled)
        self.proxy_api_key_toggle_btn.setEnabled(enabled)
        self.proxy_model_label.setEnabled(enabled)
        self.proxy_model_input.setEnabled(enabled)
        self.proxy_fallback_model_label.setEnabled(enabled)
        self.proxy_fallback_model_input.setEnabled(enabled)
        self.proxy_thinking_label.setEnabled(enabled)
        self.proxy_thinking_combo.setEnabled(enabled)

        if animate:
            self._animate_proxy_help(enabled)
        else:
            self.proxy_setup_container.setMaximumHeight(
                self._proxy_help_target_height() if enabled else 0
            )

    def _init_ui_state(self):
        """Initialize UI state based on config."""
        self._appearance_mode = self._normalize_appearance_mode(self.config.get("appearance_mode", "auto"))
        self._is_dark_theme = self._resolve_dark_theme()
        self._setup_styling()

        appearance_labels = {"auto": "Auto", "dark": "Dark", "light": "Light"}
        self.appearance_combo.blockSignals(True)
        self.appearance_combo.setCurrentText(appearance_labels[self._appearance_mode])
        self.appearance_combo.blockSignals(False)

        self._animation_fps = self._normalize_animation_fps(self.config.get("animation_fps", 100))
        self.animation_fps_combo.blockSignals(True)
        fps_text = str(self._animation_fps)
        if self.animation_fps_combo.findText(fps_text) == -1:
            self.animation_fps_combo.addItem(fps_text)
        self.animation_fps_combo.setCurrentText(fps_text)
        self.animation_fps_combo.blockSignals(False)

        use_formatter = self.config.get("use_formatter", False)
        self.format_toggle.setChecked(use_formatter)
        self.model_combo.setEnabled(use_formatter)
        self.model_label.setEnabled(use_formatter)

        self.translation_toggle.setEnabled(use_formatter)
        translation_enabled = self.config.get("translation_enabled", False) and use_formatter
        self.translation_toggle.setChecked(translation_enabled)
        self.language_input.setEnabled(translation_enabled)
        self.language_label.setEnabled(translation_enabled)

        proxy_enabled = bool(self.config.get("use_antigravity_proxy_search", False))
        self.proxy_search_toggle.blockSignals(True)
        self.proxy_search_toggle.setChecked(proxy_enabled)
        self.proxy_search_toggle.blockSignals(False)
        self.proxy_url_input.setText(
            self.config.get("antigravity_proxy_url", "http://127.0.0.1:8045")
        )
        self.proxy_api_key_input.setText(self.config.get("antigravity_api_key", ""))
        self.proxy_model_input.setText(
            self.config.get("antigravity_search_model", "gemini-3-flash")
        )
        self.proxy_fallback_model_input.setText(
            self.config.get("antigravity_search_fallback_model", "gemini-2.5-flash")
        )
        thinking_labels = {
            "high": "High",
            "medium": "Medium",
            "low": "Low",
            "none": "None",
        }
        proxy_thinking_level = self._normalize_proxy_thinking_level(
            self.config.get("antigravity_thinking_level", "high")
        )
        self.proxy_thinking_combo.blockSignals(True)
        self.proxy_thinking_combo.setCurrentText(thinking_labels[proxy_thinking_level])
        self.proxy_thinking_combo.blockSignals(False)
        self._set_proxy_settings_enabled(proxy_enabled, animate=False)

        self._refresh_pipeline_summary()
        self._refresh_theme_widgets()

    # Frameless window dragging
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()
            self._dragging = True

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def eventFilter(self, obj, event):
        if obj == getattr(self, "_header_widget", None):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
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

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and self._appearance_mode == "auto":
            refreshed_dark_mode = self._resolve_dark_theme()
            if refreshed_dark_mode != self._is_dark_theme:
                self._is_dark_theme = refreshed_dark_mode
                self._setup_styling()
                self._refresh_theme_widgets()
                self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_window_mask()
        if not self._initial_layout_applied:
            self._initial_layout_applied = True
            QTimer.singleShot(0, self._ensure_initial_layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_window_mask()

    def _update_window_mask(self):
        # Explicit rounded mask avoids compositor white-corner artifacts on some systems.
        if self.isMaximized():
            self.clearMask()
            return
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(
            float(rect.x()),
            float(rect.y()),
            float(rect.width()),
            float(rect.height()),
            24.0,
            24.0,
        )
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _ensure_initial_layout(self):
        layout = self.layout()
        if layout is None:
            return

        layout.activate()
        target_height = max(self.minimumHeight(), layout.sizeHint().height() + 2, self.height())
        if target_height != self.height():
            self.resize(self.width(), target_height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        if self._is_dark_theme:
            if self._blur_active:
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0.0, QColor(10, 16, 28, 246))
                gradient.setColorAt(1.0, QColor(15, 24, 41, 246))
                border_color = QColor(63, 91, 131, 92)
            else:
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0.0, QColor(10, 16, 28, 252))
                gradient.setColorAt(1.0, QColor(15, 24, 41, 252))
                border_color = QColor(62, 90, 128, 108)
        else:
            if self._blur_active:
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0.0, QColor(238, 242, 255, 224))
                gradient.setColorAt(1.0, QColor(226, 232, 240, 224))
                border_color = QColor(148, 163, 184, 78)
            else:
                gradient = QLinearGradient(0, 0, 0, self.height())
                gradient.setColorAt(0.0, QColor(241, 245, 249, 246))
                gradient.setColorAt(1.0, QColor(226, 232, 240, 246))
                border_color = QColor(148, 163, 184, 96)

        painter.setBrush(QBrush(gradient))
        shell_rect = self.rect().adjusted(2, 2, -2, -2)
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

    def on_animation_fps_changed(self, text):
        fps = self._normalize_animation_fps(text)
        if fps == self._animation_fps:
            return

        self._animation_fps = fps
        self.config.set("animation_fps", fps)
        self.config.save()
        self.config_changed.emit("animation_fps", fps)

    def on_proxy_search_toggle_changed(self, state):
        enabled = state == int(Qt.CheckState.Checked.value)
        self.config.set("use_antigravity_proxy_search", enabled)
        self.config.save()
        self._set_proxy_settings_enabled(enabled, animate=True)
        if enabled and self.settings_tabs.currentIndex() != 2:
            self.settings_tabs.setCurrentIndex(2)
        self.config_changed.emit("use_antigravity_proxy_search", enabled)

    def _save_proxy_field(self, key, text):
        normalized = str(text or "").strip()
        self.config.set(key, normalized)
        self.config.save()
        self.config_changed.emit(key, normalized)

    def on_proxy_url_changed(self):
        self._save_proxy_field("antigravity_proxy_url", self.proxy_url_input.text())

    def on_proxy_api_key_changed(self):
        self._save_proxy_field("antigravity_api_key", self.proxy_api_key_input.text())

    def on_proxy_model_changed(self):
        self._save_proxy_field("antigravity_search_model", self.proxy_model_input.text())

    def on_proxy_fallback_model_changed(self):
        self._save_proxy_field(
            "antigravity_search_fallback_model",
            self.proxy_fallback_model_input.text(),
        )

    def on_proxy_thinking_level_changed(self, text):
        normalized = self._normalize_proxy_thinking_level(text)
        self._save_proxy_field("antigravity_thinking_level", normalized)

    def on_proxy_api_key_toggle_visibility(self):
        showing = self.proxy_api_key_input.echoMode() == QLineEdit.EchoMode.Normal
        if showing:
            self.proxy_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.proxy_api_key_toggle_btn.setText("Show")
        else:
            self.proxy_api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.proxy_api_key_toggle_btn.setText("Hide")

    def on_force_save_clicked(self):
        if self._force_save_in_progress:
            return

        self.force_save_hide_timer.stop()
        self.force_save_fade_in.stop()
        self.force_save_fade_out.stop()
        self.force_save_feedback.setVisible(False)
        self._start_force_save_loading()
        QTimer.singleShot(320, self._complete_force_save)

    def _complete_force_save(self):
        try:
            save_result = self._persist_force_save_settings()
        except Exception:
            self._stop_force_save_loading()
            self._show_force_save_feedback("Save failed", "error")
            self._set_error_status("Save failed")
            return

        self._stop_force_save_loading()
        save_ok = True if save_result is None else bool(save_result)
        if not save_ok:
            self._show_force_save_feedback("Save failed", "error")
            self._set_error_status("Save failed")
            return

        self._emit_force_reconfigure()
        self._show_force_save_feedback("✓ Saved", "ok")

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
