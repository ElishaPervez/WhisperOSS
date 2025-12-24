from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QComboBox, QCheckBox, QTextEdit, QLineEdit, QGroupBox, QInputDialog,
    QFrame, QGraphicsDropShadowEffect, QScrollArea, QSlider, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer, QPoint, QSize, pyqtProperty
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QLinearGradient, QRadialGradient


class AnimatedToggle(QCheckBox):
    """Modern animated toggle switch"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 28)
        self._handle_position = 4
        self._animation = QPropertyAnimation(self, b"handle_position", self)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.setDuration(200)
        self.stateChanged.connect(self._animate)
        
    def _animate(self, state):
        if state:
            self._animation.setEndValue(self.width() - 24)
        else:
            self._animation.setEndValue(4)
        self._animation.start()
    
    def _get_handle_position(self):
        return self._handle_position
    
    def _set_handle_position(self, pos):
        self._handle_position = pos
        self.update()
    
    handle_position = pyqtProperty(float, _get_handle_position, _set_handle_position)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Track
        if self.isChecked():
            track_color = QColor("#4361ee")
        else:
            track_color = QColor("#3d3d5c")
        
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        
        # Handle with glow
        if self.isChecked():
            glow = QRadialGradient(self._handle_position + 10, 14, 20)
            glow.setColorAt(0, QColor(67, 97, 238, 100))
            glow.setColorAt(1, QColor(67, 97, 238, 0))
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(int(self._handle_position) - 5, -1, 30, 30)
        
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(int(self._handle_position), 4, 20, 20)


class PulsingRecordButton(QPushButton):
    """Animated record button with pulsing glow effect"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("REC")
        self.setFixedSize(90, 90)
        self.setCheckable(True)
        self._pulse_opacity = 0.0
        self._pulse_scale = 1.0
        
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_timer.start(30)
        
        self._pulse_phase = 0.0
        self._is_recording = False
        
    def setRecording(self, recording):
        self._is_recording = recording
        if recording:
            self.setText("STOP")
        else:
            self.setText("REC")
        self.update()
    
    def _update_pulse(self):
        if self._is_recording:
            import math
            self._pulse_phase += 0.1
            self._pulse_opacity = 0.3 + 0.3 * math.sin(self._pulse_phase)
            self._pulse_scale = 1.0 + 0.1 * math.sin(self._pulse_phase)
        else:
            self._pulse_opacity = max(0, self._pulse_opacity - 0.05)
            self._pulse_scale = 1.0 + (self._pulse_scale - 1.0) * 0.9
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        cx, cy = self.width() // 2, self.height() // 2
        radius = 40
        
        # Outer glow when recording
        if self._pulse_opacity > 0.01:
            glow_radius = radius * self._pulse_scale * 1.5
            glow = QRadialGradient(cx, cy, glow_radius)
            glow.setColorAt(0, QColor(239, 68, 68, int(255 * self._pulse_opacity)))
            glow.setColorAt(0.5, QColor(239, 68, 68, int(128 * self._pulse_opacity)))
            glow.setColorAt(1, QColor(239, 68, 68, 0))
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - glow_radius), int(cy - glow_radius), 
                              int(glow_radius * 2), int(glow_radius * 2))
        
        # Main button gradient
        if self._is_recording:
            gradient = QRadialGradient(cx, cy - 10, radius)
            gradient.setColorAt(0, QColor("#ff6b6b"))
            gradient.setColorAt(0.7, QColor("#ef4444"))
            gradient.setColorAt(1, QColor("#b91c1c"))
        else:
            gradient = QRadialGradient(cx, cy - 10, radius)
            gradient.setColorAt(0, QColor("#ff8585"))
            gradient.setColorAt(0.7, QColor("#ef4444"))
            gradient.setColorAt(1, QColor("#dc2626"))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor("#ffffff30"), 2))
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
        
        # Inner highlight
        highlight = QRadialGradient(cx - 10, cy - 15, radius * 0.6)
        highlight.setColorAt(0, QColor(255, 255, 255, 80))
        highlight.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(highlight))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(cx - radius + 10, cy - radius + 5, radius, radius - 10)
        
        # Text
        painter.setPen(QPen(QColor("#ffffff")))
        font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())


class GlassPanel(QFrame):
    """Glassmorphism-style panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassPanel")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Glass background
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(45, 45, 75, 180))
        gradient.setColorAt(1, QColor(30, 30, 55, 200))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 12, 12)


class MainWindow(QWidget):
    # Signals to Main Controller
    record_toggled = pyqtSignal(bool) # True=Start, False=Stop
    config_changed = pyqtSignal(str, object) # key, value

    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self.setWindowTitle("WhisperOSS")
        self.resize(380, 650)
        self._setup_styling()
        
        self.is_recording = False
        self.setup_ui()

    def _setup_styling(self):
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f0f23);
                font-family: 'Segoe UI', 'SF Pro Display', -apple-system;
                font-size: 14px;
                color: #e0e0e0;
            }
            
            QLabel {
                color: #a0a0c0;
                font-size: 12px;
                font-weight: 500;
                background: transparent;
            }
            
            QLabel#StatusLabel {
                color: #ff6b6b;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
                background: rgba(239, 68, 68, 0.15);
                border-radius: 8px;
                border: 1px solid rgba(239, 68, 68, 0.3);
            }
            
            QLabel#StatusLabelConnected {
                color: #4ade80;
                background: rgba(74, 222, 128, 0.15);
                border: 1px solid rgba(74, 222, 128, 0.3);
            }
            
            QLabel#SectionTitle {
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
                background: transparent;
                padding: 0;
                margin-bottom: 12px;
            }
            
            QComboBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(60, 60, 95, 0.8), stop:1 rgba(45, 45, 75, 0.9));
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 10px 15px;
                color: #e0e0e0;
                font-size: 13px;
                min-height: 20px;
            }
            
            QComboBox:hover {
                border: 1px solid rgba(67, 97, 238, 0.5);
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(70, 70, 105, 0.9), stop:1 rgba(55, 55, 85, 0.95));
            }
            
            QComboBox:focus {
                border: 1px solid #4361ee;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #a0a0c0;
                margin-right: 10px;
            }
            
            QComboBox QAbstractItemView {
                background: #2d2d4d;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                selection-background-color: #4361ee;
                selection-color: white;
                outline: none;
                padding: 5px;
            }
            
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                border-radius: 4px;
                margin: 2px;
            }
            
            QComboBox QAbstractItemView::item:hover {
                background: rgba(67, 97, 238, 0.3);
            }
            
            QTextEdit {
                background: rgba(30, 30, 50, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 12px;
                color: #d0d0e0;
                font-size: 13px;
                line-height: 1.5;
                selection-background-color: #4361ee;
            }
            
            QTextEdit:focus {
                border: 1px solid rgba(67, 97, 238, 0.4);
            }
            
            QPushButton#ApiKeyBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(67, 97, 238, 0.2), stop:1 rgba(67, 97, 238, 0.1));
                border: 1px solid rgba(67, 97, 238, 0.4);
                border-radius: 10px;
                padding: 12px 20px;
                color: #8ba3f7;
                font-size: 13px;
                font-weight: 600;
            }
            
            QPushButton#ApiKeyBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(67, 97, 238, 0.35), stop:1 rgba(67, 97, 238, 0.2));
                border: 1px solid rgba(67, 97, 238, 0.6);
                color: #a8bdff;
            }
            
            QPushButton#ApiKeyBtn:pressed {
                background: rgba(67, 97, 238, 0.4);
            }
            
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0;
            }
            
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                min-height: 30px;
            }
            
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # Header / API Status
        self.api_status_label = QLabel("⚠ Initializing API...")
        self.api_status_label.setObjectName("StatusLabel")
        self.api_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.api_status_label)

        # REC Button with animation
        self.record_btn = PulsingRecordButton()
        self.record_btn.clicked.connect(self.on_record_clicked)
        
        btn_container = QHBoxLayout()
        btn_container.addStretch()
        btn_container.addWidget(self.record_btn)
        btn_container.addStretch()
        layout.addLayout(btn_container)
        
        layout.addSpacing(10)

        # Configuration Section
        config_panel = GlassPanel()
        config_layout = QVBoxLayout(config_panel)
        config_layout.setSpacing(16)
        config_layout.setContentsMargins(20, 20, 20, 20)
        
        config_title = QLabel("⚙ Configuration")
        config_title.setObjectName("SectionTitle")
        config_layout.addWidget(config_title)

        # Input Device
        device_label = QLabel("MICROPHONE")
        config_layout.addWidget(device_label)
        
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        config_layout.addWidget(self.device_combo)

        # Formatter Toggle with label
        toggle_container = QHBoxLayout()
        toggle_label = QLabel("AI Formatting")
        toggle_label.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        self.format_toggle = AnimatedToggle()
        self.format_toggle.setChecked(self.config.get("use_formatter", False))
        self.format_toggle.stateChanged.connect(self.on_toggle_changed)
        toggle_container.addWidget(toggle_label)
        toggle_container.addStretch()
        toggle_container.addWidget(self.format_toggle)
        config_layout.addLayout(toggle_container)

        # Model Selector
        self.model_label = QLabel("FORMATTER MODEL")
        config_layout.addWidget(self.model_label)
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        config_layout.addWidget(self.model_combo)
        
        layout.addWidget(config_panel)

        # Transcript Section
        transcript_panel = GlassPanel()
        transcript_layout = QVBoxLayout(transcript_panel)
        transcript_layout.setSpacing(12)
        transcript_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header with Title and Copy Button
        header_layout = QHBoxLayout()

        transcript_title = QLabel("📝 Last Transcription")
        transcript_title.setObjectName("SectionTitle")
        header_layout.addWidget(transcript_title)

        header_layout.addStretch()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setFixedSize(60, 24)
        self.copy_btn.setToolTip("Copy transcription to clipboard")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                color: #e0e0e0;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.05);
            }
        """)
        self.copy_btn.clicked.connect(self.copy_log_to_clipboard)
        header_layout.addWidget(self.copy_btn)

        transcript_layout.addLayout(header_layout)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMinimumHeight(120)
        self.log_display.setPlaceholderText("Transcribed text will appear here...")
        transcript_layout.addWidget(self.log_display)
        
        layout.addWidget(transcript_panel)
        
        layout.addStretch()
        
        # API Key Button
        self.api_key_btn = QPushButton("🔑 Set API Key")
        self.api_key_btn.setObjectName("ApiKeyBtn")
        self.api_key_btn.clicked.connect(self.prompt_api_key)
        self.api_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.api_key_btn)

    def on_record_clicked(self, checked):
        self.is_recording = checked
        self.record_btn.setRecording(checked)
        self.record_toggled.emit(checked)

    def set_recording_state(self, is_recording):
        self.is_recording = is_recording
        self.record_btn.setChecked(is_recording)
        self.record_btn.setRecording(is_recording)

    def on_device_changed(self, index):
        device_id = self.device_combo.itemData(index)
        self.config.set("input_device_index", device_id)
        self.config_changed.emit("input_device_index", device_id)

    def on_toggle_changed(self, state):
        enabled = (state == 2) # Qt.CheckState.Checked
        self.config.set("use_formatter", enabled)
        self.model_combo.setEnabled(enabled)
        self.model_label.setEnabled(enabled)

    def on_model_changed(self, text):
        if text:
            self.config.set("formatter_model", text)

    def update_log(self, text):
        self.log_display.setText(text)

    def copy_log_to_clipboard(self):
        text = self.log_display.toPlainText()
        if not text:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(text)

        # Feedback animation
        original_text = "Copy"
        self.copy_btn.setText("Copied!")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(74, 222, 128, 0.2);
                border: 1px solid rgba(74, 222, 128, 0.4);
                border-radius: 4px;
                color: #a3e635;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        self.copy_btn.setEnabled(False)

        QTimer.singleShot(1500, lambda: self._reset_copy_btn(original_text))

    def _reset_copy_btn(self, original_text):
        self.copy_btn.setText(original_text)
        self.copy_btn.setEnabled(True)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                color: #e0e0e0;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.05);
            }
        """)

    def prompt_api_key(self):
        text, ok = QInputDialog.getText(self, "Groq API Key", "Enter your Groq API Key:", text=self.config.get("api_key", ""))
        if ok and text:
            self.config.set("api_key", text)
            self.config_changed.emit("api_key", text)
            self._set_connected_status("API Key Updated")

    def set_device_list(self, devices):
        self.device_combo.clear()
        current_dev = self.config.get("input_device_index")
        for i, (idx, name) in enumerate(devices):
            self.device_combo.addItem(name, idx)
            if idx == current_dev:
                self.device_combo.setCurrentIndex(i)

    def set_model_list(self, models):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        
        current = self.config.get("formatter_model")
        if current in models:
            self.model_combo.setCurrentText(current)
        
        self.model_combo.blockSignals(False)
    
    def _set_connected_status(self, text):
        self.api_status_label.setText(f"✓ {text}")
        self.api_status_label.setStyleSheet("""
            color: #4ade80;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 16px;
            background: rgba(74, 222, 128, 0.15);
            border-radius: 8px;
            border: 1px solid rgba(74, 222, 128, 0.3);
        """)
    
    def _set_error_status(self, text):
        self.api_status_label.setText(f"⚠ {text}")
        self.api_status_label.setStyleSheet("""
            color: #ff6b6b;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 16px;
            background: rgba(239, 68, 68, 0.15);
            border-radius: 8px;
            border: 1px solid rgba(239, 68, 68, 0.3);
        """)
