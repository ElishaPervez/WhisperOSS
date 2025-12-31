from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QComboBox, QCheckBox, QTextEdit, QLineEdit, QGroupBox, QInputDialog,
    QFrame, QGraphicsDropShadowEffect, QScrollArea, QSlider, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer, QPoint, QSize, pyqtProperty, QEvent
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

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Track
        if self.isChecked():
            track_color = QColor("#007AFF") # iOS Blue
        else:
            track_color = QColor("#E5E5EA") # iOS Gray
        
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        
        # Handle with shadow
        painter.setBrush(QBrush(QColor("#ffffff")))
        
        # Draw handle
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
        self.setWindowTitle("WhisperOSS Settings")
        self.resize(340, 480)
        
        # Track if blur effect is active
        self._blur_active = False
        
        # Translucent Background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint) # Optional: Frameless looks cleaner with translucent
        
        # Apply Windows Acrylic Blur Effect (Liquid Glass)
        self._apply_blur_effect()
        
        self._setup_styling()
        
        self.is_recording = False
        self.setup_ui()
        self._init_ui_state()

        # Window dragging for frameless
        self.oldPos = self.pos()
    
    def _apply_blur_effect(self):
        """Apply Windows DWM Acrylic blur effect after window is ready."""
        try:
            from src.window_effects import WindowEffect
            self._window_effect = WindowEffect()
            # Delay to ensure window handle exists, then apply and track result
            def apply_and_track():
                self._blur_active = self._window_effect.set_acrylic(self.winId())
                if self._blur_active:
                    self.update()  # Repaint without background
            QTimer.singleShot(100, apply_and_track)
        except ImportError:
            pass  # Module not available

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()
            self._dragging = True

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def mouseMoveEvent(self, event):
        if hasattr(self, '_dragging') and self._dragging:
            delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()
    
    def eventFilter(self, obj, event):
        """Handle drag events from header widget."""
        if obj == getattr(self, '_header_widget', None):
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.oldPos = event.globalPosition().toPoint()
                    self._dragging = True
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._dragging = False
                return True
            elif event.type() == QEvent.Type.MouseMove:
                if hasattr(self, '_dragging') and self._dragging:
                    delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
                    self.move(self.x() + delta.x(), self.y() + delta.y())
                    self.oldPos = event.globalPosition().toPoint()
                    return True
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self._blur_active:
            # When blur is active, draw a very subtle semi-transparent overlay
            # This keeps the window clickable while showing the blur behind
            bg_color = QColor(255, 255, 255, 30)  # Very low opacity to show blur
            painter.setBrush(QBrush(bg_color))
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
            painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1), 20, 20)
        else:
            # Fallback: White background with 80% opacity
            bg_color = QColor(255, 255, 255, 215) # 215/255 approx 84%
            painter.setBrush(QBrush(bg_color))
            painter.setPen(QPen(QColor(0, 0, 0, 20), 1)) # Subtle border
            painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1), 20, 20)

    def _setup_styling(self):
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', 'SF Pro Display', -apple-system;
                font-size: 13px;
                color: #1c1c1e;
            }
            
            QLabel {
                color: #3a3a3c;
                font-weight: 500;
            }
            
            QLabel#SectionTitle {
                color: #000000;
                font-size: 16px;
                font-weight: 700;
                margin-bottom: 8px;
            }

            QComboBox {
                background: rgba(235, 235, 240, 0.8);
                border: 1px solid rgba(0, 0, 0, 0.05);
                border-radius: 10px;
                padding: 8px 12px;
                color: #1c1c1e;
                min-height: 20px;
            }
            
            QComboBox:hover {
                background: rgba(225, 225, 230, 0.9);
            }
            
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }

            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                selection-background-color: #007AFF;
                selection-color: white;
                border-radius: 8px;
                padding: 4px;
            }

            QLineEdit {
                background: rgba(235, 235, 240, 0.8);
                border: 1px solid rgba(0, 0, 0, 0.05);
                border-radius: 10px;
                padding: 8px 12px;
                color: #1c1c1e;
            }

            QPushButton#SaveBtn {
                background-color: #007AFF;
                color: white;
                border-radius: 12px;
                padding: 12px;
                font-weight: 600;
                border: none;
            }

            QPushButton#SaveBtn:hover {
                background-color: #0062cc;
            }
            
            QPushButton#CloseBtn {
                background: transparent;
                color: #8e8e93;
                font-size: 18px;
                font-weight: bold;
                border: none;
            }
            QPushButton#CloseBtn:hover {
                color: #ff3b30;
            }
        """)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header: Draggable area with Title + Close Button
        header_widget = QWidget()
        header_widget.setFixedHeight(40)
        header_widget.setCursor(Qt.CursorShape.SizeAllCursor)  # Show drag cursor
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("WhisperOSS")
        title.setObjectName("SectionTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)  # Normal cursor for button
        close_btn.clicked.connect(self.close) 
        header_layout.addWidget(close_btn)
        
        # Store reference and add the widget (not layout)
        self._header_widget = header_widget
        header_widget.installEventFilter(self)  # Enable dragging from header
        layout.addWidget(header_widget)

        # --- Configuration Fields ---

        # Input Device
        layout.addWidget(QLabel("MICROPHONE"))
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        layout.addWidget(self.device_combo)

        layout.addSpacing(8)

        # Formatter Toggle
        toggle_container = QHBoxLayout()
        toggle_label = QLabel("AI Formatting")
        self.format_toggle = AnimatedToggle()
        self.format_toggle.setChecked(self.config.get("use_formatter", False))
        self.format_toggle.stateChanged.connect(self.on_toggle_changed)
        toggle_container.addWidget(toggle_label)
        toggle_container.addStretch()
        toggle_container.addWidget(self.format_toggle)
        layout.addLayout(toggle_container)

        # Translation Toggle
        translate_container = QHBoxLayout()
        translate_label = QLabel("Translation")
        self.translation_toggle = AnimatedToggle()
        self.translation_toggle.setChecked(self.config.get("translation_enabled", False))
        self.translation_toggle.stateChanged.connect(self.on_translate_toggle_changed)
        translate_container.addWidget(translate_label)
        translate_container.addStretch()
        translate_container.addWidget(self.translation_toggle)
        layout.addLayout(translate_container)

        layout.addSpacing(8)
        
        # Target Language
        self.language_label = QLabel("TARGET LANGUAGE")
        layout.addWidget(self.language_label)
        self.language_input = QLineEdit()
        self.language_input.setText(self.config.get("target_language", "English"))
        self.language_input.setPlaceholderText("e.g. Spanish, French, Urdu")
        self.language_input.textChanged.connect(self.on_language_changed)
        layout.addWidget(self.language_input)

        # Formatting Style
        self.style_label = QLabel("FORMATTING STYLE")
        layout.addWidget(self.style_label)
        self.style_combo = QComboBox()
        from src.prompts import FORMATTING_STYLES
        self.style_combo.addItems(FORMATTING_STYLES)
        current_style = self.config.get("formatting_style", "Default")
        if current_style in FORMATTING_STYLES:
            self.style_combo.setCurrentText(current_style)
        self.style_combo.currentTextChanged.connect(self.on_style_changed)
        layout.addWidget(self.style_combo)

        # Formatter Model
        self.model_label = QLabel("FORMATTER MODEL")
        layout.addWidget(self.model_label)
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        layout.addWidget(self.model_combo)
        
        layout.addStretch()

        # Save Button
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.clicked.connect(self.on_save_clicked)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.save_btn)


    def _init_ui_state(self):
        """Initialize UI state based on config."""
        use_formatter = self.config.get("use_formatter", False)
        self.format_toggle.setChecked(use_formatter)
        self.model_combo.setEnabled(use_formatter)
        self.model_label.setEnabled(use_formatter)
        self.style_combo.setEnabled(use_formatter)
        self.style_label.setEnabled(use_formatter)

        translation_enabled = self.config.get("translation_enabled", False)
        self.translation_toggle.setChecked(translation_enabled)
        self.language_input.setEnabled(translation_enabled)
        self.language_label.setEnabled(translation_enabled)

    # --- Event Handlers ---

    # NOTE: Record button removed, so no on_record_clicked handler needed here.
    # Recording is controlled via hotkeys or tray (if we see one). 
    # But controller still calls set_recording_state on window, so we need a stub.
    
    def on_record_clicked(self, checked):
        # Stub: Main window no longer initiates recording via button
        self.is_recording = checked
        self.record_toggled.emit(checked) 

    def set_recording_state(self, is_recording):
        # Stub: Only updates internal state, no button to update
        self.is_recording = is_recording

    def on_device_changed(self, index):
        if index < 0: return
        device_id = self.device_combo.itemData(index)
        self.config.set("input_device_index", device_id)
        self.config_changed.emit("input_device_index", device_id)

    def on_toggle_changed(self, state):
        enabled = (state == 2) # Qt.CheckState.Checked
        self.config.set("use_formatter", enabled)
        self.model_combo.setEnabled(enabled)
        self.model_label.setEnabled(enabled)
        self.style_combo.setEnabled(enabled)
        self.style_label.setEnabled(enabled)
        
        # Translation depends on AI Formatting
        if not enabled:
            self.translation_toggle.blockSignals(True)
            self.translation_toggle.setChecked(False)
            self.config.set("translation_enabled", False)
            self.translation_toggle.blockSignals(False)
            self.translation_toggle.setEnabled(False)
            self.language_input.setEnabled(False)
            self.language_label.setEnabled(False)
        else:
            self.translation_toggle.setEnabled(True)
            trans_enabled = self.translation_toggle.isChecked()
            self.language_input.setEnabled(trans_enabled)
            self.language_label.setEnabled(trans_enabled)

    def on_translate_toggle_changed(self, state):
        enabled = (state == 2)
        self.config.set("translation_enabled", enabled)
        self.language_input.setEnabled(enabled)
        self.language_label.setEnabled(enabled)

    def on_language_changed(self, text):
        self.config.set("target_language", text)

    def on_style_changed(self, text):
        self.config.set("formatting_style", text)

    def on_model_changed(self, text):
        if text:
            self.config.set("formatter_model", text)

    def on_save_clicked(self):
        """Persist current UI states to disk config."""
        # Ensure latest values are in config (already done by handlers, but for safety)
        self.config.set("use_formatter", self.format_toggle.isChecked())
        self.config.set("translation_enabled", self.translation_toggle.isChecked())
        self.config.set("target_language", self.language_input.text())
        self.config.set("formatting_style", self.style_combo.currentText())
        
        model = self.model_combo.currentText()
        if model:
            self.config.set("formatter_model", model)
            
        # Write to disk
        self.config.save()
            
        # Visual feedback on button
        original_text = "Save Settings"
        self.save_btn.setText("Saved!")
        QTimer.singleShot(1000, lambda: self.save_btn.setText(original_text))

    def update_log(self, text):
        # Stub: No log display anymore
        pass



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
        # Logic kept just in case, but button removed
        text, ok = QInputDialog.getText(self, "Groq API Key", "Enter your Groq API Key:", text=self.config.get("api_key", ""))
        if ok and text:
            self.config.set("api_key", text)
            self.config_changed.emit("api_key", text)

    def set_device_list(self, devices):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        current_dev = self.config.get("input_device_index")
        for i, (idx, name) in enumerate(devices):
            self.device_combo.addItem(name, idx)
            if idx == current_dev:
                self.device_combo.setCurrentIndex(i)
        self.device_combo.blockSignals(False)

    def set_model_list(self, models):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        
        current = self.config.get("formatter_model")
        if current in models:
            self.model_combo.setCurrentText(current)
        
        self.model_combo.blockSignals(False)
    
    def _set_connected_status(self, text):
        # This method is no longer used as status label is removed
        pass
    
    def _set_error_status(self, text):
        # This method is no longer used as status label is removed
        pass