from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QFrame,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, QTimer, QRect, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QBrush,
    QPen,
    QFont,
    QLinearGradient,
    QRadialGradient,
    QTextDocument,
)
from typing import Optional
import math
import re
import time

from src.debug_trace import trace_widget_event


def _normalize_animation_fps(value, default: int = 100) -> int:
    try:
        fps = int(value)
    except (TypeError, ValueError):
        fps = int(default)
    return max(30, min(240, fps))


def _interval_from_fps(fps: int) -> int:
    return max(4, int(round(1000 / float(_normalize_animation_fps(fps)))))


class CompactAudioVisualizer(QWidget):
    """Compact 12-bar audio visualizer matching the reference design"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)  # More compact height
        self.setMinimumWidth(120)
        
        # Visual state
        self.amplitude = 0.0
        self.target_amplitude = 0.0
        
        # 12 bars for compact look
        self.bar_count = 12
        self.bar_amplitudes = [0.0] * self.bar_count
        self.bar_targets = [0.0] * self.bar_count
        self.bar_phases = [i * 0.3 for i in range(self.bar_count)]
        
        # Animation phase for idle animation
        self.idle_phase = 0.0
        self.is_active = False
        self.mode = "idle"  # idle | listening | processing | success
        self.processing_phase = 0.0
        self.success_progress = 0.0
        self.processing_mix = 0.0  # 0=bars only, 1=loader only
        self.processing_text = ""
        
        # Smooth animation timer
        self._animation_fps = 100
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(_interval_from_fps(self._animation_fps))

        self._status_font = QFont(self.font())
        self._status_font.setWeight(QFont.Weight.DemiBold)
        if self._status_font.pointSizeF() > 0:
            self._status_font.setPointSizeF(self._status_font.pointSizeF() + 0.3)

    def set_animation_fps(self, fps: int):
        self._animation_fps = _normalize_animation_fps(fps, self._animation_fps)
        self.timer.setInterval(_interval_from_fps(self._animation_fps))

    def set_mode(self, mode: str):
        """Switch animation mode for recording lifecycle transitions."""
        # "completing" kept as alias for backward compatibility.
        if mode == "completing":
            mode = "success"

        if mode not in {"idle", "listening", "processing", "success"}:
            return

        self.mode = mode
        if mode == "idle":
            self.target_amplitude = 0.0
            self.is_active = False
            self.processing_mix = 0.0
            self.processing_text = ""
        elif mode == "listening":
            self.is_active = False
            self.processing_mix = 0.0
            self.processing_text = ""
        elif mode == "processing":
            self.processing_phase = 0.0
            self.target_amplitude = 0.42
            self.is_active = True
            # Processing UI is text-only; keep bars fully faded out.
            self.processing_mix = 1.0
        elif mode == "success":
            # Start slightly progressed so the completion state is immediately
            # distinguishable from the processing loader.
            self.success_progress = 0.05
            self.target_amplitude = 0.0
            self.is_active = False
            self.processing_text = ""
            # Start from mostly loader-visible to morph into the checkmark.
            self.processing_mix = max(self.processing_mix, 0.74)

    def set_processing_text(self, text: str):
        cleaned = " ".join(str(text or "").split()).strip()
        if len(cleaned) > 96:
            cleaned = cleaned[:93].rstrip() + "..."
        if cleaned == self.processing_text:
            return
        self.processing_text = cleaned
        if self.mode == "processing":
            self.update()

    def preferred_processing_width(self, min_width: int = 120, max_width: int = 460) -> int:
        base_min = max(120, int(min_width))
        base_max = max(base_min, int(max_width))
        text = self.processing_text
        if not text:
            return base_min
        text_width = self.fontMetrics().horizontalAdvance(text)
        side_padding = 22
        return max(base_min, min(base_max, text_width + side_padding))
        
    def update_level(self, level):
        """Level is expected to be 0.0 to 1.0"""
        if self.mode in {"processing", "success"}:
            return

        self.mode = "listening"
        shaped = min(1.0, (max(level, 0.0) ** 0.65) * 1.35)
        self.target_amplitude = shaped
        self.is_active = level > 0.008
        
        # Distribute to individual bars with wave-like variation
        for i in range(self.bar_count):
            # Create wave pattern - middle bars higher
            center = self.bar_count / 2
            distance_from_center = abs(i - center) / center
            height_modifier = 1.0 - (distance_from_center * 0.48)
            
            variation = 0.68 + 0.46 * math.sin((self.idle_phase * 2.4) + self.bar_phases[i])
            self.bar_targets[i] = self.target_amplitude * variation * height_modifier

    def animate(self):
        # Global amplitude lerp
        if self.mode == "listening" and self.is_active:
            self.amplitude += (self.target_amplitude - self.amplitude) * 0.34
        else:
            self.amplitude += (self.target_amplitude - self.amplitude) * 0.16
        
        # Idle animation phase
        self.idle_phase += 0.06

        center = (self.bar_count - 1) / 2.0

        if self.mode == "processing":
            # Slightly slower cadence so processing feels calm/readable.
            self.processing_phase += 0.045
            self.processing_mix = min(1.0, self.processing_mix + 0.06)

            for i in range(self.bar_count):
                distance = abs(i - center) / max(center, 1.0)
                # Traveling wave + breathing base so users see ongoing API work.
                travel = 0.25 + 0.55 * (0.5 + 0.5 * math.sin(self.processing_phase - i * 0.62))
                base = 0.16 + (0.14 * (1.0 - distance))
                self.bar_targets[i] = min(1.0, base + travel * (0.72 - 0.28 * distance))
                self.bar_amplitudes[i] += (self.bar_targets[i] - self.bar_amplitudes[i]) * 0.20
            self.update()
            return

        if self.mode == "success":
            # Morph the loader into a final checkmark state.
            self.processing_phase += 0.04
            # Run completion ~1.5x faster for a snappier finish.
            self.success_progress = min(1.0, self.success_progress + 0.0072)
            self.processing_mix = min(1.0, self.processing_mix + 0.08)

            for i in range(self.bar_count):
                self.bar_targets[i] = 0.0
                self.bar_amplitudes[i] += (self.bar_targets[i] - self.bar_amplitudes[i]) * 0.22
            self.update()
            return
        
        # Individual bar animations
        self.processing_mix = max(0.0, self.processing_mix - 0.14)

        for i in range(self.bar_count):
            # Add subtle idle movement when not active
            if not self.is_active:
                distance_from_center = abs(i - center) / max(center, 1.0)
                height_mod = 1.0 - (distance_from_center * 0.5)
                idle_movement = (0.1 + 0.15 * math.sin(self.idle_phase + self.bar_phases[i])) * height_mod
                self.bar_targets[i] = idle_movement
            
            # Fast attack, gentler decay for a snappier "live" feel.
            target_delta = self.bar_targets[i] - self.bar_amplitudes[i]
            if self.is_active:
                base_speed = 0.34 if target_delta > 0 else 0.19
                lerp_speed = base_speed + 0.02 * (i % 3)
            else:
                lerp_speed = 0.12 + 0.02 * (i % 3)
            self.bar_amplitudes[i] += (self.bar_targets[i] - self.bar_amplitudes[i]) * lerp_speed
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Draw fully opaque black background pill.
        painter.setBrush(QBrush(QColor(0, 0, 0, 255)))
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
        painter.drawRoundedRect(0, 0, w, h, h // 2, h // 2)  # Pill shape
        
        # Bar configuration - compact narrow bars
        bar_width = 4
        bar_spacing = 3
        total_bars_width = (self.bar_count * bar_width) + ((self.bar_count - 1) * bar_spacing)
        start_x = (w - total_bars_width) / 2
        max_bar_height = h - 10  # Reduced padding for compact look
        min_bar_height = 4
        
        bar_alpha = max(0.0, 1.0 - self.processing_mix)
        for i in range(self.bar_count):
            amp = self.bar_amplitudes[i]
            bar_height = min_bar_height + (max_bar_height - min_bar_height) * amp
            bar_height = max(min_bar_height, min(max_bar_height, bar_height))
            
            x = start_x + i * (bar_width + bar_spacing)
            y = (h - bar_height) / 2
            
            # Glow effect when active
            glow_intensity = amp * 0.7
            if glow_intensity > 0.1 and bar_alpha > 0.01:
                glow_color = QColor(255, 255, 255, int(40 * glow_intensity * bar_alpha))  # White glow
                painter.setBrush(QBrush(glow_color))
                painter.setPen(Qt.PenStyle.NoPen)
                glow_padding = 2
                painter.drawRoundedRect(
                    int(x - glow_padding), 
                    int(y - glow_padding), 
                    int(bar_width + glow_padding * 2), 
                    int(bar_height + glow_padding * 2), 
                    3, 3
                )
            
            # Main bar - solid white
            if bar_alpha > 0.01:
                painter.setBrush(QBrush(QColor(255, 255, 255, int(230 * bar_alpha))))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height), 2, 2)

        # Processing state: centered text with a slow moving glow sweep.
        text_alpha = self.processing_mix
        if self.mode == "processing" and text_alpha > 0.01:
            status_text = self.processing_text.strip() or "Processing"
            text_rect = QRect(10, 0, max(18, w - 20), int(h))

            painter.save()
            painter.setFont(self._status_font)
            fm = painter.fontMetrics()
            elided = fm.elidedText(
                status_text,
                Qt.TextElideMode.ElideRight,
                text_rect.width(),
            )

            # Base text weight for readability.
            painter.setPen(QPen(QColor(255, 255, 255, int(196 * text_alpha)), 1))
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                elided,
            )

            # Slow left-right sweep.
            sweep = 0.08 + (0.84 * (0.5 + 0.5 * math.sin(self.processing_phase * 0.55)))
            lead = max(0.0, sweep - 0.20)
            trail = min(1.0, sweep + 0.20)
            glow_gradient = QLinearGradient(float(text_rect.left()), 0.0, float(text_rect.right()), 0.0)
            glow_gradient.setColorAt(0.0, QColor(255, 255, 255, int(28 * text_alpha)))
            glow_gradient.setColorAt(lead, QColor(255, 255, 255, int(58 * text_alpha)))
            glow_gradient.setColorAt(sweep, QColor(255, 255, 255, int(255 * text_alpha)))
            glow_gradient.setColorAt(trail, QColor(255, 255, 255, int(58 * text_alpha)))
            glow_gradient.setColorAt(1.0, QColor(255, 255, 255, int(28 * text_alpha)))
            painter.setPen(QPen(QBrush(glow_gradient), 1))
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                elided,
            )
            painter.restore()

        if self.mode == "success":
            # Final checkmark state shown briefly before fade-out.
            reveal = min(1.0, self.success_progress / 0.45)
            # Keep success elements fully visible once revealed; let the widget
            # opacity fade handle the final disappearance so both fade together.
            success_alpha = reveal
            if success_alpha > 0.01:
                cx = w - 16.0
                cy = h / 2.0
                radius = 7.3

                # Heartbeat-like line that travels toward the final checkmark.
                line_left = 18.0
                line_right = cx - radius - 5.5
                line_mid = (line_left + line_right) / 2.0
                line_points = [
                    (line_left, cy),
                    (line_mid - 11.0, cy),
                    (line_mid - 6.0, cy - 1.6),
                    (line_mid - 2.0, cy + 3.4),
                    (line_mid + 3.0, cy - 4.8),
                    (line_mid + 8.0, cy + 1.5),
                    (line_right, cy),
                ]
                line_reveal = min(1.0, self.success_progress / 0.62)
                if line_reveal > 0.01:
                    line_pen = QPen(
                        QColor(255, 255, 255, int(220 * success_alpha)),
                        1.35,
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,
                    )
                    painter.setPen(line_pen)
                    segment_count = len(line_points) - 1
                    for idx in range(segment_count):
                        seg_start = idx / segment_count
                        seg_end = (idx + 1) / segment_count
                        x1, y1 = line_points[idx]
                        x2, y2 = line_points[idx + 1]
                        if line_reveal >= seg_end:
                            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
                            continue
                        if line_reveal > seg_start:
                            t = (line_reveal - seg_start) / max(0.0001, (seg_end - seg_start))
                            xt = x1 + (x2 - x1) * t
                            yt = y1 + (y2 - y1) * t
                            painter.drawLine(int(x1), int(y1), int(xt), int(yt))
                        break

                glow = QRadialGradient(cx, cy, radius + 3.4)
                glow.setColorAt(0.0, QColor(255, 255, 255, int(120 * success_alpha)))
                glow.setColorAt(1.0, QColor(255, 255, 255, 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(glow))
                painter.drawEllipse(int(cx - (radius + 3.4)), int(cy - (radius + 3.4)), int((radius + 3.4) * 2), int((radius + 3.4) * 2))

                ring_pen = QPen(QColor(255, 255, 255, int(165 * success_alpha)), 1.2)
                painter.setPen(ring_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))

                p1 = (cx - 4.2, cy + 0.4)
                p2 = (cx - 1.4, cy + 3.2)
                p3 = (cx + 4.8, cy - 3.0)

                check_pen = QPen(
                    QColor(255, 255, 255, int(255 * success_alpha)),
                    1.9,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
                painter.setPen(check_pen)

                # Slightly delay check reveal so line sweep lands into it.
                check_reveal = min(1.0, max(0.0, (self.success_progress - 0.22) / 0.52))
                if check_reveal <= 0.45:
                    t = check_reveal / 0.45
                    x = p1[0] + (p2[0] - p1[0]) * t
                    y = p1[1] + (p2[1] - p1[1]) * t
                    painter.drawLine(int(p1[0]), int(p1[1]), int(x), int(y))
                else:
                    painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
                    t = (check_reveal - 0.45) / 0.55
                    x = p2[0] + (p3[0] - p2[0]) * t
                    y = p2[1] + (p3[1] - p2[1]) * t
                    painter.drawLine(int(p2[0]), int(p2[1]), int(x), int(y))


# Keep AudioVisualizer for backward compatibility if needed as overlay
class AudioVisualizer(QWidget):
    """Floating audio visualizer overlay with compact bar design and fade animation."""

    COMPACT_WIDTH = 120
    COMPACT_HEIGHT = 36
    PROCESSING_MIN_WIDTH = 120
    PROCESSING_MAX_WIDTH = 460
    PROCESSING_RESIZE_FRAMES = 8
    CARD_MIN_WIDTH = 214
    CARD_MAX_WIDTH = 640
    CARD_MIN_HEIGHT = 74
    CARD_MAX_HEIGHT = 260
    CARD_MAX_WIDTH_RATIO = 0.90
    CARD_MAX_HEIGHT_RATIO = 0.70
    ANSWER_AUTO_DISMISS_MS = 50_000
    ANSWER_REVEAL_DELAY_FRAMES = 10
    ANSWER_EXPAND_FRAMES = 40
    ANSWER_COLLAPSE_FRAMES = 24
    ANSWER_COMPLETION_HOLD_FRAMES = 150
    STREAM_WORD_FADE_MS = 320.0
    STREAM_WORD_OVERLAP_RATIO = 0.30
    STREAM_MAX_LAG_MS = 3000.0
    STREAM_COMPLETION_TARGET_MS = 3000.0
    STREAM_MIN_WORD_STEP_MS = 42.0
    STREAM_TEXT_FADE_MIN_OPACITY = 0.70

    def __init__(self, animation_fps: int = 100):
        super().__init__()
        self._click_through = True
        self._apply_window_flags()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(self.COMPACT_WIDTH, self.COMPACT_HEIGHT)

        self._visualizer = CompactAudioVisualizer(self)
        self._visualizer.resize(self.COMPACT_WIDTH, self.COMPACT_HEIGHT)

        self._answer_visible = False
        self._answer_text_pending = ""
        self._answer_anchor_rect = QRect()
        self._processing_step_text = ""
        self._drag_origin = None
        self._streaming_answer_active = False
        self._streaming_answer_dismissed = False
        self._streaming_answer_text = ""
        self._streaming_pending_text: Optional[str] = None
        self._streaming_target_rect = QRect()
        self._streaming_visible_text = ""
        self._streaming_arrived_segments: list[str] = []
        self._streaming_visible_segments = 0
        self._streaming_reveal_carry = 0.0
        self._streaming_last_tick_ts = 0.0
        self._streaming_auto_follow = True
        self._streaming_scroll_by_user = False
        self._answer_scroll_programmatic = False
        self._streaming_anchor_center_x = 0
        self._streaming_anchor_bottom_y = 0
        self._streaming_anchor_valid = False

        # Frame-driven transform animation so motion cadence follows configured FPS.
        self._transition_timer = QTimer(self)
        self._transition_timer.timeout.connect(self._animate_widget_geometry_step)
        self._transition_start_rect = QRect()
        self._transition_end_rect = QRect()
        self._transition_frames = 0
        self._transition_frame_index = 0
        self._transition_easing = QEasingCurve(QEasingCurve.Type.Linear)
        self._transition_has_opacity = False
        self._transition_start_opacity = 1.0
        self._transition_end_opacity = 1.0
        self._transition_on_finished = None

        self._build_answer_card()

        # Fade animation setup for compact recording mode.
        self._opacity = 0.0
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._animate_fade)
        self._fade_target = 0.0
        self._is_showing = False
        self._animation_fps = _normalize_animation_fps(animation_fps)

        self._hide_after_completion_timer = QTimer(self)
        self._hide_after_completion_timer.setSingleShot(True)
        self._hide_after_completion_timer.timeout.connect(self.hide)
        self._auto_dismiss_timer = QTimer(self)
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.timeout.connect(self.dismiss_answer)
        self._answer_reveal_timer = QTimer(self)
        self._answer_reveal_timer.setSingleShot(True)
        self._answer_reveal_timer.timeout.connect(self._begin_answer_reveal)
        self._streaming_resize_timer = QTimer(self)
        self._streaming_resize_timer.setSingleShot(False)
        self._streaming_resize_timer.timeout.connect(self._tick_streaming_answer_frame)
        self.set_animation_fps(self._animation_fps)
        self._sync_child_geometry()

    def _trace_widget_event(self, event: str, trigger: str, reason: str = "", **details):
        try:
            trace_widget_event(event, trigger=trigger, reason=reason, **details)
        except Exception:
            pass

    def _build_answer_card(self):
        self._answer_card = QWidget(self)
        self._answer_card.setObjectName("AnswerCard")
        self._answer_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._answer_card.hide()

        self._answer_surface_hpad = 10
        self._answer_surface_vpad = 8

        self._answer_body_container = QWidget()
        self._answer_body_container.setObjectName("AnswerBodySurface")
        self._answer_body_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._answer_label = QLabel()
        self._answer_label.setObjectName("AnswerBody")
        self._answer_label.setWordWrap(True)
        self._answer_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._answer_label.setTextFormat(Qt.TextFormat.MarkdownText)
        self._answer_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._answer_label.setMinimumWidth(1)
        self._answer_text_opacity = QGraphicsOpacityEffect(self._answer_label)
        self._answer_text_opacity.setOpacity(1.0)
        self._answer_label.setGraphicsEffect(self._answer_text_opacity)

        self._answer_text_fade_anim = QPropertyAnimation(self._answer_text_opacity, b"opacity", self)
        self._answer_text_fade_anim.setDuration(int(self.STREAM_WORD_FADE_MS))
        self._answer_text_fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        body_layout = QVBoxLayout(self._answer_body_container)
        body_layout.setContentsMargins(
            self._answer_surface_hpad,
            self._answer_surface_vpad,
            self._answer_surface_hpad,
            self._answer_surface_vpad,
        )
        body_layout.setSpacing(0)
        body_layout.addWidget(self._answer_label)

        self._answer_scroll = QScrollArea(self._answer_card)
        self._answer_scroll.setObjectName("AnswerScroll")
        self._answer_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._answer_scroll.setWidgetResizable(False)
        self._answer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._answer_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._answer_scroll.setWidget(self._answer_body_container)
        self._answer_scroll.viewport().setAutoFillBackground(False)
        self._answer_scroll.viewport().setStyleSheet("background: transparent; border: none;")

        scroll_bar = self._answer_scroll.verticalScrollBar()
        scroll_bar.sliderPressed.connect(self._on_answer_scroll_slider_pressed)
        scroll_bar.valueChanged.connect(self._on_answer_scroll_value_changed)

        self._seen_button = QPushButton("Seen", self._answer_card)
        self._seen_button.setObjectName("SeenButton")
        self._seen_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._seen_button.clicked.connect(self.dismiss_answer)

        layout = QVBoxLayout(self._answer_card)
        layout.setContentsMargins(16, 11, 16, 10)
        layout.setSpacing(7)
        layout.addWidget(self._answer_scroll)

        row = QHBoxLayout()
        row.setContentsMargins(0, 3, 0, 0)
        row.addStretch(1)
        row.addWidget(self._seen_button)
        layout.addLayout(row)

        self._answer_card.setStyleSheet(
            """
            QWidget#AnswerCard {
                background: rgb(0, 0, 0);
                border: none;
                border-radius: 16px;
            }
            QWidget#AnswerBodySurface {
                background: transparent;
                border: none;
                border-radius: 0px;
            }
            QScrollArea#AnswerScroll {
                background: transparent;
                border: none;
            }
            QLabel#AnswerBody {
                color: rgba(248, 249, 251, 246);
                font-size: 13px;
                font-weight: 500;
                line-height: 1.32;
            }
            QPushButton#SeenButton {
                background: rgba(255, 255, 255, 11);
                color: rgba(248, 250, 254, 242);
                border: none;
                border-radius: 11px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 600;
                min-height: 23px;
            }
            QPushButton#SeenButton:hover {
                background: rgba(255, 255, 255, 17);
            }
            QPushButton#SeenButton:pressed {
                background: rgba(255, 255, 255, 25);
            }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 2px 0 2px 0;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 52);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            """
        )

    def _on_answer_scroll_slider_pressed(self):
        if not self._answer_visible:
            return
        self._streaming_scroll_by_user = True
        self._streaming_auto_follow = False

    def _on_answer_scroll_value_changed(self, value: int):
        if not self._answer_visible or self._answer_scroll_programmatic:
            return
        scroll_bar = self._answer_scroll.verticalScrollBar()
        if scroll_bar.maximum() <= 0:
            return
        if value < (scroll_bar.maximum() - 2):
            self._streaming_scroll_by_user = True
            self._streaming_auto_follow = False

    def _scroll_answer_to_bottom(self, force: bool = False):
        if not force and not self._streaming_auto_follow:
            return
        scroll_bar = self._answer_scroll.verticalScrollBar()
        if scroll_bar.maximum() <= 0:
            return
        self._answer_scroll_programmatic = True
        try:
            scroll_bar.setValue(scroll_bar.maximum())
        finally:
            self._answer_scroll_programmatic = False

    def _set_answer_text_opacity(self, opacity: float):
        self._answer_text_fade_anim.stop()
        self._answer_text_opacity.setOpacity(max(0.0, min(1.0, float(opacity))))

    def _trigger_streaming_text_fade(self, revealed_count: int):
        if revealed_count <= 0:
            return
        current = float(self._answer_text_opacity.opacity())
        dip = min(0.22, 0.055 + (0.04 * float(revealed_count)))
        start_opacity = max(self.STREAM_TEXT_FADE_MIN_OPACITY, current - dip)
        self._answer_text_fade_anim.stop()
        self._answer_text_opacity.setOpacity(start_opacity)
        self._answer_text_fade_anim.setDuration(int(self.STREAM_WORD_FADE_MS))
        self._answer_text_fade_anim.setStartValue(start_opacity)
        self._answer_text_fade_anim.setEndValue(1.0)
        self._answer_text_fade_anim.start()

    def _apply_window_flags(self):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        if self._click_through:
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)

    def _set_click_through(self, enabled: bool):
        enabled = bool(enabled)
        if self._click_through == enabled:
            return
        geometry = self.geometry()
        was_visible = self.isVisible()
        self._click_through = enabled
        self._apply_window_flags()
        if was_visible:
            super().show()
            self.setGeometry(geometry)
            self.setWindowOpacity(self._opacity)
        self._sync_child_geometry()

    def _screen_geometry_for_rect(self, reference_rect: QRect) -> QRect:
        app = self.window().windowHandle().screen() if self.window().windowHandle() else None
        if app is not None:
            return app.availableGeometry()
        try:
            from PyQt6.QtWidgets import QApplication

            screen = QApplication.screenAt(reference_rect.center())
            if screen is None:
                screen = QApplication.primaryScreen()
            if screen is not None:
                return screen.availableGeometry()
        except Exception:
            pass
        return QRect(0, 0, 1920, 1080)

    def _sync_child_geometry(self):
        bounds = self.rect()
        self._visualizer.setGeometry(bounds)
        self._answer_card.setGeometry(bounds)

    def _reset_streaming_answer_state(self, clear_dismissed: bool = True):
        self._streaming_answer_active = False
        self._streaming_answer_text = ""
        self._streaming_visible_text = ""
        self._streaming_arrived_segments = []
        self._streaming_visible_segments = 0
        self._streaming_reveal_carry = 0.0
        self._streaming_last_tick_ts = 0.0
        self._streaming_auto_follow = True
        self._streaming_scroll_by_user = False
        self._answer_scroll_programmatic = False
        self._streaming_anchor_center_x = 0
        self._streaming_anchor_bottom_y = 0
        self._streaming_anchor_valid = False
        self._set_answer_text_opacity(1.0)
        self._streaming_pending_text = None
        self._streaming_target_rect = QRect()
        if self._streaming_resize_timer.isActive():
            self._streaming_resize_timer.stop()
        if clear_dismissed:
            self._streaming_answer_dismissed = False

    def _streaming_anchor_reference_rect(self, fallback: QRect) -> QRect:
        base = QRect(fallback)
        if not self._streaming_anchor_valid:
            return base
        width = max(1, base.width())
        height = max(1, base.height())
        x = int(round(float(self._streaming_anchor_center_x) - (float(width) / 2.0)))
        y = int(round(float(self._streaming_anchor_bottom_y) - float(height) + 1.0))
        return QRect(x, y, width, height)

    @staticmethod
    def _split_streaming_segments(text: str) -> list[str]:
        source = str(text or "")
        if not source:
            return []
        segments: list[str] = []
        cursor = 0
        for match in re.finditer(r"\S+\s*", source):
            prefix = source[cursor:match.start()]
            token = f"{prefix}{match.group(0)}"
            if token:
                segments.append(token)
            cursor = match.end()
        if cursor < len(source):
            tail = source[cursor:]
            if segments:
                segments[-1] += tail
            else:
                segments.append(tail)
        return segments

    def _set_streaming_arrived_text(self, text: str):
        latest = str(text or "")
        append_only = latest.startswith(self._streaming_answer_text)
        self._streaming_answer_text = latest
        self._streaming_arrived_segments = self._split_streaming_segments(latest)
        total = len(self._streaming_arrived_segments)

        if not append_only:
            # Fallback for unexpected non-append diffs: keep already revealed
            # prefix length when possible, then continue forward.
            self._streaming_reveal_carry = 0.0
        self._streaming_visible_segments = min(self._streaming_visible_segments, total)

    def _streaming_word_step_ms(self, backlog_segments: int) -> float:
        base_step = max(
            self.STREAM_MIN_WORD_STEP_MS,
            self.STREAM_WORD_FADE_MS * max(0.05, (1.0 - self.STREAM_WORD_OVERLAP_RATIO)),
        )
        step_ms = base_step

        if backlog_segments > 0 and self._streaming_answer_active:
            lag_ms = float(backlog_segments) * base_step
            if lag_ms > self.STREAM_MAX_LAG_MS:
                catch_up_step = base_step * (self.STREAM_MAX_LAG_MS / lag_ms)
                step_ms = min(step_ms, max(self.STREAM_MIN_WORD_STEP_MS, catch_up_step))

        if backlog_segments > 0 and (not self._streaming_answer_active):
            completion_step = self.STREAM_COMPLETION_TARGET_MS / float(backlog_segments)
            step_ms = min(step_ms, max(self.STREAM_MIN_WORD_STEP_MS, completion_step))

        return max(self.STREAM_MIN_WORD_STEP_MS, step_ms)

    @staticmethod
    def _streaming_geometry_lerp_factor(elapsed_ms: float) -> float:
        if elapsed_ms <= 0:
            return 0.1
        factor = 1.0 - math.exp(-float(elapsed_ms) / 130.0)
        return max(0.08, min(0.30, factor))

    def _tick_streaming_answer_frame(self):
        now = time.monotonic()
        if self._streaming_last_tick_ts <= 0.0:
            self._streaming_last_tick_ts = now
        elapsed_ms = max(0.0, (now - self._streaming_last_tick_ts) * 1000.0)
        self._streaming_last_tick_ts = now

        if self._streaming_pending_text is not None:
            next_text = self._streaming_pending_text
            self._streaming_pending_text = None
            if next_text != self._streaming_answer_text:
                self._set_streaming_arrived_text(next_text)

        total_segments = len(self._streaming_arrived_segments)
        visible_segments = min(self._streaming_visible_segments, total_segments)
        backlog_segments = max(0, total_segments - visible_segments)
        reveal_count = 0

        if backlog_segments > 0:
            step_ms = self._streaming_word_step_ms(backlog_segments)
            reveal_progress = self._streaming_reveal_carry + (elapsed_ms / max(1.0, step_ms))
            reveal_count = int(reveal_progress)
            self._streaming_reveal_carry = reveal_progress - reveal_count
            if reveal_count > 0:
                visible_segments = min(total_segments, visible_segments + reveal_count)
                self._streaming_visible_segments = visible_segments
        else:
            self._streaming_reveal_carry = 0.0
            self._streaming_visible_segments = visible_segments

        visible_text = "".join(self._streaming_arrived_segments[: self._streaming_visible_segments])
        if visible_text != self._streaming_visible_text:
            self._streaming_visible_text = visible_text
            self._answer_label.setText(self._streaming_visible_text)
            self._trigger_streaming_text_fade(reveal_count)

        target = QRect(self._streaming_target_rect)
        reference = QRect(self.geometry())
        if reference.width() <= 0 or reference.height() <= 0:
            reference = QRect(self.x(), self.y(), self.CARD_MIN_WIDTH, self.CARD_MIN_HEIGHT)
        anchored_reference = self._streaming_anchor_reference_rect(reference)

        if target.width() <= 0 or target.height() <= 0:
            target = self._answer_rect_for_reference(
                anchored_reference,
                self._streaming_visible_text or " ",
            )
            self._streaming_target_rect = QRect(target)
        else:
            self._streaming_target_rect = self._answer_rect_for_reference(
                anchored_reference,
                self._streaming_visible_text or " ",
            )
            target = QRect(self._streaming_target_rect)

        current = QRect(self.geometry())
        if current.width() <= 0 or current.height() <= 0:
            current = QRect(target)
            self.setGeometry(current)

        if (not self._transition_timer.isActive()) and current != target:
            factor = self._streaming_geometry_lerp_factor(elapsed_ms)
            nx = int(round(current.x() + (target.x() - current.x()) * factor))
            ny = int(round(current.y() + (target.y() - current.y()) * factor))
            nw = int(round(current.width() + (target.width() - current.width()) * factor))
            nh = int(round(current.height() + (target.height() - current.height()) * factor))

            if (
                abs(target.x() - nx) <= 1
                and abs(target.y() - ny) <= 1
                and abs(target.width() - nw) <= 1
                and abs(target.height() - nh) <= 1
            ):
                self.setGeometry(target)
            else:
                self.setGeometry(nx, ny, nw, nh)
            self._sync_child_geometry()

        self._scroll_answer_to_bottom()

        reveal_complete = (
            (not self._streaming_answer_active)
            and (self._streaming_pending_text is None)
            and (self._streaming_visible_segments >= len(self._streaming_arrived_segments))
        )
        if reveal_complete and self._answer_visible and (not self._auto_dismiss_timer.isActive()):
            self._auto_dismiss_timer.start(self.ANSWER_AUTO_DISMISS_MS)

        if (
            reveal_complete
            and self.geometry() == self._streaming_target_rect
            and not self._transition_timer.isActive()
        ):
            self._streaming_resize_timer.stop()

    def resizeEvent(self, event):
        self._sync_child_geometry()
        super().resizeEvent(event)

    def _stop_answer_transition(self):
        if self._transition_timer.isActive():
            self._transition_timer.stop()
        self._transition_on_finished = None

    def _duration_for_frames(self, frames: int) -> int:
        frames = max(1, int(frames))
        return max(90, int(round((1000.0 * frames) / float(self._animation_fps))))

    @staticmethod
    def _strip_markdown_for_metrics(text: str) -> str:
        raw = str(text or "")
        raw = re.sub(r"`([^`]*)`", r"\1", raw)
        raw = re.sub(r"\*\*([^*]+)\*\*", r"\1", raw)
        raw = re.sub(r"__([^_]+)__", r"\1", raw)
        raw = re.sub(r"\*([^*]+)\*", r"\1", raw)
        raw = re.sub(r"_([^_]+)_", r"\1", raw)
        raw = re.sub(r"^\s*[-*+]\s+", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"^\s*\d+\.\s+", "", raw, flags=re.MULTILINE)
        return raw

    @staticmethod
    def _contains_markdown_markup(text: str) -> bool:
        sample = str(text or "")
        if re.search(r"(^|\n)\s*[-*+]\s+\S", sample):
            return True
        if re.search(r"(^|\n)\s*\d+\.\s+\S", sample):
            return True
        return any(token in sample for token in ("**", "__", "`", "~~"))

    @staticmethod
    def _normalize_markdown_bold_spacing(text: str) -> str:
        source = str(text or "")
        if "**" not in source:
            return source

        def _trim_bold_inner(match):
            inner = match.group(1)
            trimmed = inner.strip()
            if not trimmed:
                return match.group(0)
            return f"**{trimmed}**"

        # Normalize malformed bold markers like "** name**" or "**name **"
        # so QLabel Markdown rendering keeps the intended emphasis.
        return re.sub(r"\*\*([^\n]+?)\*\*", _trim_bold_inner, source)

    def _create_markdown_document(self, text: str) -> QTextDocument:
        doc = QTextDocument()
        doc.setDocumentMargin(0.0)
        doc.setDefaultFont(self._answer_label.font())
        doc.setMarkdown(str(text or ""))
        return doc

    def _measure_wrapped_text(self, text: str, text_width: int) -> tuple[float, int]:
        width = max(1, int(text_width))
        doc = self._create_markdown_document(text)
        doc.setTextWidth(float(width))
        measured_height = float(doc.size().height())
        line_height = max(1.0, float(self._answer_label.fontMetrics().lineSpacing()))
        estimated_lines = max(1, int(math.ceil(measured_height / line_height)))
        return measured_height, estimated_lines

    def _measure_rendered_label_height(self, text: str, text_width: int) -> int:
        width = max(1, int(text_width))
        markdown_height, _ = self._measure_wrapped_text(text, width)

        # QLabel Markdown rendering can diverge from QTextDocument height for
        # list-heavy text; prefer the larger measured height to avoid clipping.
        rendered_height = self._answer_label.heightForWidth(width)
        if rendered_height <= 0:
            rendered_height = self._answer_label.sizeHint().height()
        return max(1, int(math.ceil(max(markdown_height, float(rendered_height)))))

    def _pick_text_width(self, text: str, max_text_width: int) -> int:
        max_text_width = max(120, int(max_text_width))
        min_text_width = min(max_text_width, max(156, int(max_text_width * 0.32)))
        plain_text = self._strip_markdown_for_metrics(text)
        natural_width = max(
            1,
            max(
                self._answer_label.fontMetrics().horizontalAdvance(line)
                for line in (plain_text.splitlines() or [""])
            ),
        )
        has_markup = self._contains_markdown_markup(text) or ("\n" in text)

        # Keep short answers as slim single-line cards.
        if (not has_markup) and natural_width <= int(max_text_width * 0.78):
            return int(max(min_text_width, min(max_text_width, natural_width + 10)))

        best_width = max_text_width
        best_score = None
        step = 6 if max_text_width - min_text_width < 170 else 8

        for width in range(min_text_width, max_text_width + 1, step):
            text_height, line_count = self._measure_wrapped_text(text, width)
            if line_count <= 0:
                continue

            fill_ratio = min(1.0, float(natural_width) / max(1.0, float(width)))

            if line_count <= 2:
                density_penalty = 0.0
            else:
                density_penalty = 0.95 + (line_count - 2) * 1.25

            height_penalty = text_height / 680.0
            width_penalty = (float(width) / float(max_text_width)) * 0.08

            score = density_penalty + ((1.0 - fill_ratio) * 0.64) + height_penalty + width_penalty

            if best_score is None or score < best_score:
                best_score = score
                best_width = width

        return int(best_width)

    def _compact_rect_for_reference(self, reference_rect: QRect) -> QRect:
        screen_geo = self._screen_geometry_for_rect(reference_rect)
        center_x = reference_rect.center().x()
        bottom_y = reference_rect.bottom()

        width = self.COMPACT_WIDTH
        height = self.COMPACT_HEIGHT
        margin = 8

        x = center_x - (width // 2)
        y = bottom_y - height + 1

        min_x = screen_geo.x() + margin
        max_x = screen_geo.x() + screen_geo.width() - width - margin
        min_y = screen_geo.y() + margin
        max_y = screen_geo.y() + screen_geo.height() - height - margin

        if max_x >= min_x:
            x = max(min_x, min(x, max_x))
        if max_y >= min_y:
            y = max(min_y, min(y, max_y))

        return QRect(int(x), int(y), width, height)

    def _processing_rect_for_reference(self, reference_rect: QRect, text: str) -> QRect:
        screen_geo = self._screen_geometry_for_rect(reference_rect)
        center_x = reference_rect.center().x()
        bottom_y = reference_rect.bottom()

        has_text = bool(" ".join(str(text or "").split()).strip())
        min_width = self.PROCESSING_MIN_WIDTH if has_text else self.COMPACT_WIDTH
        self._visualizer.set_processing_text(text)
        width = self._visualizer.preferred_processing_width(
            min_width=min_width,
            max_width=self.PROCESSING_MAX_WIDTH,
        )
        height = self.COMPACT_HEIGHT
        margin = 8

        x = center_x - (width // 2)
        y = bottom_y - height + 1

        min_x = screen_geo.x() + margin
        max_x = screen_geo.x() + screen_geo.width() - width - margin
        min_y = screen_geo.y() + margin
        max_y = screen_geo.y() + screen_geo.height() - height - margin

        if max_x >= min_x:
            x = max(min_x, min(x, max_x))
        if max_y >= min_y:
            y = max(min_y, min(y, max_y))

        return QRect(int(x), int(y), int(width), int(height))

    def _answer_rect_for_reference(self, reference_rect: QRect, answer: str) -> QRect:
        screen_geo = self._screen_geometry_for_rect(reference_rect)
        max_width = max(
            self.CARD_MIN_WIDTH,
            min(
                max(self.CARD_MIN_WIDTH, int(screen_geo.width() * self.CARD_MAX_WIDTH_RATIO)),
                max(self.CARD_MIN_WIDTH, screen_geo.width() - 24),
            ),
        )

        layout = self._answer_card.layout()
        margins = layout.contentsMargins()
        horizontal_padding = margins.left() + margins.right()
        vertical_padding = margins.top() + margins.bottom()
        layout_spacing = layout.spacing()
        surface_horizontal = self._answer_surface_hpad * 2
        surface_vertical = self._answer_surface_vpad * 2

        max_text_width = max(120, max_width - horizontal_padding - surface_horizontal)
        text_width = self._pick_text_width(answer, max_text_width)
        self._answer_label.setText(str(answer or ""))
        label_height = self._measure_rendered_label_height(answer, text_width)

        button_width = self._seen_button.sizeHint().width()
        button_height = self._seen_button.sizeHint().height()
        target_body_width = text_width + surface_horizontal
        target_width = max(target_body_width + horizontal_padding, button_width + horizontal_padding + 4)
        target_width = max(self.CARD_MIN_WIDTH, min(max_width, int(target_width)))
        target_body_width = max(1, target_width - horizontal_padding)

        button_row_height = max(24, button_height) + layout_spacing + 6
        max_height = max(
            self.CARD_MIN_HEIGHT,
            min(
                max(self.CARD_MIN_HEIGHT, int(screen_geo.height() * self.CARD_MAX_HEIGHT_RATIO)),
                max(self.CARD_MIN_HEIGHT, screen_geo.height() - 24),
            ),
        )
        max_body_height = max(28, max_height - vertical_padding - button_row_height)
        full_body_height = label_height + surface_vertical
        body_height = min(full_body_height, max_body_height)
        self._answer_label.setFixedWidth(max(1, target_body_width - surface_horizontal))
        self._answer_label.setMinimumHeight(label_height)
        self._answer_label.setMaximumHeight(label_height)
        self._answer_body_container.setFixedSize(target_body_width, full_body_height)
        self._answer_scroll.setMinimumHeight(max(24, body_height))
        self._answer_scroll.setMaximumHeight(max(24, max_body_height))

        target_height = body_height + vertical_padding + button_row_height
        target_height = max(self.CARD_MIN_HEIGHT, min(max_height, target_height))

        center_x = reference_rect.center().x()
        bottom_y = reference_rect.bottom()
        margin = 12

        x = center_x - (target_width // 2)
        y = bottom_y - target_height + 1

        min_x = screen_geo.x() + margin
        max_x = screen_geo.x() + screen_geo.width() - target_width - margin
        min_y = screen_geo.y() + margin
        max_y = screen_geo.y() + screen_geo.height() - target_height - margin

        if max_x >= min_x:
            x = max(min_x, min(x, max_x))
        if max_y >= min_y:
            y = max(min_y, min(y, max_y))

        return QRect(int(x), int(y), int(target_width), int(target_height))

    def _animate_widget_geometry(
        self,
        start_rect: QRect,
        end_rect: QRect,
        frames: int,
        easing: QEasingCurve.Type,
        fade_end: Optional[float] = None,
        on_finished=None,
    ):
        self._stop_answer_transition()
        self._transition_start_rect = QRect(start_rect)
        self._transition_end_rect = QRect(end_rect)
        self._transition_frames = max(1, int(frames))
        self._transition_frame_index = 0
        self._transition_easing = QEasingCurve(easing)
        self._transition_has_opacity = fade_end is not None
        self._transition_start_opacity = float(self.windowOpacity())
        self._transition_end_opacity = float(self._transition_start_opacity if fade_end is None else fade_end)
        self._transition_on_finished = on_finished

        self.setGeometry(self._transition_start_rect)
        if self._transition_has_opacity:
            self.setWindowOpacity(self._transition_start_opacity)
            self._opacity = self._transition_start_opacity

        if not self._transition_timer.isActive():
            self._transition_timer.start(_interval_from_fps(self._animation_fps))

    def _animate_widget_geometry_step(self):
        if self._transition_frames <= 0:
            self._stop_answer_transition()
            return

        self._transition_frame_index += 1
        progress = min(1.0, self._transition_frame_index / float(self._transition_frames))
        eased = float(self._transition_easing.valueForProgress(progress))

        sx = self._transition_start_rect.x()
        sy = self._transition_start_rect.y()
        sw = self._transition_start_rect.width()
        sh = self._transition_start_rect.height()
        ex = self._transition_end_rect.x()
        ey = self._transition_end_rect.y()
        ew = self._transition_end_rect.width()
        eh = self._transition_end_rect.height()

        nx = int(round(sx + (ex - sx) * eased))
        ny = int(round(sy + (ey - sy) * eased))
        nw = int(round(sw + (ew - sw) * eased))
        nh = int(round(sh + (eh - sh) * eased))
        self.setGeometry(nx, ny, nw, nh)

        if self._transition_has_opacity:
            opacity = self._transition_start_opacity + (
                (self._transition_end_opacity - self._transition_start_opacity) * eased
            )
            self._opacity = float(opacity)
            self.setWindowOpacity(self._opacity)

        if progress >= 1.0:
            self._transition_timer.stop()
            self.setGeometry(self._transition_end_rect)
            if self._transition_has_opacity:
                self._opacity = float(self._transition_end_opacity)
                self.setWindowOpacity(self._opacity)
            callback = self._transition_on_finished
            self._transition_on_finished = None
            if callback is not None:
                callback()

    def _animate_fade(self):
        """Smooth fade animation step."""
        diff = self._fade_target - self._opacity
        if abs(diff) < 0.02:
            self._opacity = self._fade_target
            self._fade_timer.stop()
            if self._opacity <= 0:
                super().hide()
                self._visualizer.set_mode("idle")
        else:
            # Slower fade-out than fade-in for a more graceful exit.
            lerp = 0.17 if diff > 0 else 0.055
            self._opacity += diff * lerp
        self.setWindowOpacity(self._opacity)

    def set_animation_fps(self, fps: int):
        self._animation_fps = _normalize_animation_fps(fps, self._animation_fps)
        self._visualizer.set_animation_fps(self._animation_fps)
        self._fade_timer.setInterval(_interval_from_fps(self._animation_fps))
        self._transition_timer.setInterval(_interval_from_fps(self._animation_fps))
        self._streaming_resize_timer.setInterval(_interval_from_fps(self._animation_fps))

    def show(self):
        """Show with fade in animation."""
        self._trace_widget_event(
            "widget_show",
            "AudioVisualizer.show",
            reason="visualizer requested to show",
        )
        self._hide_after_completion_timer.stop()
        self._answer_reveal_timer.stop()
        if not self._is_showing:
            self._is_showing = True
            self._opacity = 0.0
            self.setWindowOpacity(0.0)
            super().show()
        self._fade_target = 1.0
        if not self._fade_timer.isActive():
            self._fade_timer.start(_interval_from_fps(self._animation_fps))

    def hide(self, reason: str = ""):
        """Hide with fade out animation."""
        self._trace_widget_event(
            "widget_hide",
            "AudioVisualizer.hide",
            reason=reason or "hide requested",
        )
        self._hide_after_completion_timer.stop()
        self._auto_dismiss_timer.stop()
        self._processing_step_text = ""
        self._visualizer.set_processing_text("")
        if self._answer_reveal_timer.isActive():
            self._answer_reveal_timer.stop()
            self._answer_text_pending = ""
        if self._answer_visible:
            self.dismiss_answer()
            return
        self._reset_streaming_answer_state(clear_dismissed=False)
        self._is_showing = False
        self._fade_target = 0.0
        if not self._fade_timer.isActive():
            self._fade_timer.start(_interval_from_fps(self._animation_fps))

    def _reset_answer_state_immediately(self):
        self._auto_dismiss_timer.stop()
        self._answer_reveal_timer.stop()
        self._answer_text_pending = ""
        self._reset_streaming_answer_state(clear_dismissed=True)
        if (
            not self._answer_visible
            and not self._answer_card.isVisible()
            and not self._transition_timer.isActive()
        ):
            return
        self._stop_answer_transition()
        self._answer_visible = False
        self._answer_card.hide()
        self._answer_label.clear()
        self._visualizer.show()
        self._visualizer.set_mode("idle")
        self._processing_step_text = ""
        self._visualizer.set_processing_text("")
        compact_rect = self._compact_rect_for_reference(self.geometry())
        self.setGeometry(compact_rect)
        self._sync_child_geometry()
        self._set_click_through(True)
        self._opacity = 1.0 if self.isVisible() else 0.0
        self.setWindowOpacity(self._opacity)

    def begin_streaming_answer(self, reason: str = ""):
        if self._streaming_answer_dismissed:
            return
        self._trace_widget_event(
            "widget_stream_answer_begin",
            "AudioVisualizer.begin_streaming_answer",
            reason=reason or "streaming answer started",
        )
        self._hide_after_completion_timer.stop()
        self._auto_dismiss_timer.stop()
        self._answer_reveal_timer.stop()
        self._fade_timer.stop()
        self._stop_answer_transition()
        self._reset_streaming_answer_state(clear_dismissed=False)

        if not self.isVisible():
            self._is_showing = True
            self._opacity = 1.0
            self.setWindowOpacity(1.0)
            super().show()

        start_rect = QRect(self.geometry())
        if start_rect.width() <= 0 or start_rect.height() <= 0:
            start_rect = QRect(self.x(), self.y(), self.COMPACT_WIDTH, self.COMPACT_HEIGHT)
            self.setGeometry(start_rect)
        self._streaming_anchor_center_x = int(start_rect.center().x())
        self._streaming_anchor_bottom_y = int(start_rect.bottom())
        self._streaming_anchor_valid = True

        self._streaming_answer_active = True
        self._answer_visible = True
        self._set_click_through(False)
        self._answer_text_pending = ""
        self._answer_label.setText("")
        self._set_answer_text_opacity(1.0)
        self._answer_card.show()
        self._answer_card.raise_()
        self._visualizer.hide()
        self._streaming_last_tick_ts = time.monotonic()
        self._streaming_auto_follow = True
        self._streaming_scroll_by_user = False
        self._scroll_answer_to_bottom(force=True)

        initial_reference = self._streaming_anchor_reference_rect(start_rect)
        self._streaming_target_rect = self._answer_rect_for_reference(
            initial_reference,
            " ",
        )
        self._animate_widget_geometry(
            start_rect=start_rect,
            end_rect=self._streaming_target_rect,
            frames=max(10, int(self.ANSWER_EXPAND_FRAMES * 0.45)),
            easing=QEasingCurve.Type.OutCubic,
        )
        if not self._streaming_resize_timer.isActive():
            self._streaming_resize_timer.start()

    def update_streaming_answer(self, text: str, reason: str = ""):
        if self._streaming_answer_dismissed:
            return
        rendered = self._normalize_markdown_bold_spacing(str(text or ""))
        if not rendered:
            return
        if not self._streaming_answer_active:
            self.begin_streaming_answer(reason=reason or "streaming answer update")
        if rendered == self._streaming_answer_text and self._streaming_pending_text is None:
            return

        self._streaming_pending_text = rendered
        if not self._streaming_resize_timer.isActive():
            self._streaming_resize_timer.start()

    def complete_streaming_answer(self, final_text: str = "", reason: str = ""):
        if self._streaming_answer_dismissed:
            self._streaming_answer_active = False
            return
        self._trace_widget_event(
            "widget_stream_answer_complete",
            "AudioVisualizer.complete_streaming_answer",
            reason=reason or "streaming answer completed",
            answer_preview=str(final_text or "")[:120],
        )
        if final_text:
            self.update_streaming_answer(final_text, reason="final streamed answer sync")

        self._streaming_answer_active = False
        if not self._answer_visible:
            return
        if not self._streaming_resize_timer.isActive():
            self._streaming_resize_timer.start()
        self._tick_streaming_answer_frame()

    def show_answer(self, answer: str, reason: str = ""):
        text = self._normalize_markdown_bold_spacing((answer or "").strip()) or "No answer available."
        self._trace_widget_event(
            "widget_answer_transition_start",
            "AudioVisualizer.show_answer",
            reason=reason or "answer received",
            answer_preview=text[:120],
        )

        self._hide_after_completion_timer.stop()
        self._auto_dismiss_timer.stop()
        self._answer_reveal_timer.stop()
        self._fade_timer.stop()
        self._stop_answer_transition()
        self._reset_answer_state_immediately()
        self._visualizer.set_mode("success")
        self._processing_step_text = ""
        self._visualizer.set_processing_text("")
        self._answer_text_pending = text

        if not self.isVisible():
            self._is_showing = True
            self._opacity = 1.0
            self.setWindowOpacity(1.0)
            super().show()
        else:
            self._is_showing = True
            self._opacity = 1.0
            self.setWindowOpacity(1.0)

        start_rect = self.geometry()
        if start_rect.width() <= 0 or start_rect.height() <= 0:
            start_rect = QRect(self.x(), self.y(), self.COMPACT_WIDTH, self.COMPACT_HEIGHT)
            self.setGeometry(start_rect)
        self._answer_anchor_rect = QRect(start_rect)
        self._answer_visible = False
        self._answer_card.hide()
        self._visualizer.show()
        self._set_click_through(True)

        reveal_delay_ms = self._duration_for_frames(self.ANSWER_REVEAL_DELAY_FRAMES)
        self._answer_reveal_timer.start(reveal_delay_ms)

    def _begin_answer_reveal(self):
        text = (self._answer_text_pending or "").strip()
        if not text:
            return
        self._trace_widget_event(
            "widget_answer_reveal",
            "AudioVisualizer._begin_answer_reveal",
            reason="answer reveal timer fired",
            answer_preview=text[:120],
        )

        start_rect = QRect(self._answer_anchor_rect)
        if start_rect.width() <= 0 or start_rect.height() <= 0:
            start_rect = QRect(self.geometry())

        self._set_click_through(False)
        self._answer_visible = True
        self._answer_text_pending = ""
        self._answer_label.setText(text)
        self._set_answer_text_opacity(1.0)
        self._answer_card.show()
        self._answer_card.raise_()
        self._visualizer.hide()
        self._streaming_auto_follow = True
        self._streaming_scroll_by_user = False
        self._scroll_answer_to_bottom(force=True)

        target_rect = self._answer_rect_for_reference(start_rect, text)
        self._animate_widget_geometry(
            start_rect=start_rect,
            end_rect=target_rect,
            frames=self.ANSWER_EXPAND_FRAMES,
            easing=QEasingCurve.Type.OutCubic,
        )
        self._auto_dismiss_timer.start(self.ANSWER_AUTO_DISMISS_MS)

    def _finish_answer_collapse(self):
        self._stop_answer_transition()
        self._answer_visible = False
        self._answer_card.hide()
        self._answer_label.clear()
        self._answer_text_pending = ""
        self._processing_step_text = ""
        self._visualizer.set_processing_text("")
        compact_rect = self._compact_rect_for_reference(self.geometry())
        self.setGeometry(compact_rect)
        self._visualizer.show()
        self._visualizer.set_mode("success")
        self._is_showing = True
        self._opacity = 1.0
        self.setWindowOpacity(1.0)
        self._set_click_through(True)
        self._hide_after_completion_timer.stop()
        self.play_completion_and_hide(delay_ms=self._duration_for_frames(self.ANSWER_COMPLETION_HOLD_FRAMES))
        self._sync_child_geometry()

    def dismiss_answer(self, reason: str = ""):
        self._trace_widget_event(
            "widget_answer_dismiss",
            "AudioVisualizer.dismiss_answer",
            reason=reason or "dismiss requested",
            answer_visible=self._answer_visible,
        )
        if self._streaming_answer_active:
            # During live streaming, allow users to dismiss the UI without
            # interrupting the in-flight request. Ignore further chunks
            # for this response cycle.
            self._streaming_answer_active = False
            self._streaming_answer_dismissed = True
            self._reset_streaming_answer_state(clear_dismissed=False)
            self._answer_visible = False
            self._answer_card.hide()
            self._answer_label.clear()
            self._set_click_through(True)
            self.hide(reason=reason or "streaming answer dismissed")
            return

        if not self._answer_visible:
            if self._answer_reveal_timer.isActive():
                self._answer_reveal_timer.stop()
                self._answer_text_pending = ""
            self.hide(reason="dismiss invoked before answer visible")
            return

        self._auto_dismiss_timer.stop()
        self._answer_reveal_timer.stop()
        self._hide_after_completion_timer.stop()
        self._fade_timer.stop()
        self._is_showing = True
        self._fade_target = 1.0

        start_rect = self.geometry()
        end_rect = self._compact_rect_for_reference(start_rect)
        self._animate_widget_geometry(
            start_rect=start_rect,
            end_rect=end_rect,
            frames=self.ANSWER_COLLAPSE_FRAMES,
            easing=QEasingCurve.Type.InOutCubic,
            on_finished=self._finish_answer_collapse,
        )

    def update_level(self, level):
        if self._answer_visible:
            return
        self._visualizer.update_level(level)

    def set_listening_mode(self, reason: str = ""):
        self._trace_widget_event(
            "widget_mode_change",
            "AudioVisualizer.set_listening_mode",
            reason=reason or "listening mode requested",
            target_mode="listening",
        )
        self._hide_after_completion_timer.stop()
        self._reset_answer_state_immediately()
        self._processing_step_text = ""
        self._visualizer.set_processing_text("")
        self._visualizer.set_mode("listening")
        current = QRect(self.geometry())
        if current.width() <= 0 or current.height() <= 0:
            current = QRect(self.x(), self.y(), self.COMPACT_WIDTH, self.COMPACT_HEIGHT)
        target = self._compact_rect_for_reference(current)
        self.setGeometry(target)
        self._sync_child_geometry()

    def set_processing_mode(self, step_text: str = "Processing", reason: str = ""):
        self._trace_widget_event(
            "widget_mode_change",
            "AudioVisualizer.set_processing_mode",
            reason=reason or "processing mode requested",
            target_mode="processing",
            step_text=step_text,
        )
        self._hide_after_completion_timer.stop()
        self._reset_answer_state_immediately()
        self._visualizer.set_mode("processing")
        self.set_processing_step(step_text, animate=False, reason="processing mode bootstrap")

    def set_processing_step(self, step_text: str, animate: bool = True, reason: str = ""):
        normalized = " ".join(str(step_text or "").split()).strip()
        if len(normalized) > 96:
            normalized = normalized[:93].rstrip() + "..."
        if normalized == self._processing_step_text:
            self._trace_widget_event(
                "widget_processing_step_skipped",
                "AudioVisualizer.set_processing_step",
                reason=reason or "step unchanged",
                step_text=normalized,
            )
            return

        previous = self._processing_step_text
        self._processing_step_text = normalized
        self._visualizer.set_processing_text(normalized)
        self._trace_widget_event(
            "widget_processing_step_changed",
            "AudioVisualizer.set_processing_step",
            reason=reason or "processing step updated",
            previous_step=previous,
            step_text=normalized,
            animate=animate,
        )

        if self._answer_visible or self._visualizer.mode != "processing":
            self._trace_widget_event(
                "widget_processing_step_skipped",
                "AudioVisualizer.set_processing_step",
                reason="widget not in processing state",
                answer_visible=self._answer_visible,
                mode=self._visualizer.mode,
            )
            return
        if not self.isVisible():
            self._trace_widget_event(
                "widget_processing_step_skipped",
                "AudioVisualizer.set_processing_step",
                reason="widget hidden",
            )
            return

        start_rect = QRect(self.geometry())
        if start_rect.width() <= 0 or start_rect.height() <= 0:
            start_rect = QRect(self.x(), self.y(), self.COMPACT_WIDTH, self.COMPACT_HEIGHT)
            self.setGeometry(start_rect)

        target_rect = self._processing_rect_for_reference(start_rect, normalized)
        if target_rect == self.geometry():
            self._sync_child_geometry()
            return

        if animate:
            self._animate_widget_geometry(
                start_rect=start_rect,
                end_rect=target_rect,
                frames=self.PROCESSING_RESIZE_FRAMES,
                easing=QEasingCurve.Type.InOutCubic,
            )
        else:
            self.setGeometry(target_rect)
            self._sync_child_geometry()

    def play_completion_and_hide(self, delay_ms: int = 1500, reason: str = ""):
        self._trace_widget_event(
            "widget_completion",
            "AudioVisualizer.play_completion_and_hide",
            reason=reason or "completion animation requested",
            delay_ms=delay_ms,
        )
        self._auto_dismiss_timer.stop()
        self._answer_reveal_timer.stop()
        self._stop_answer_transition()
        self._processing_step_text = ""
        self._visualizer.set_processing_text("")
        current = QRect(self.geometry())
        if current.width() < self.COMPACT_WIDTH or current.height() != self.COMPACT_HEIGHT:
            if current.width() <= 0 or current.height() <= 0:
                current = QRect(self.x(), self.y(), self.COMPACT_WIDTH, self.COMPACT_HEIGHT)
            compact_rect = self._compact_rect_for_reference(current)
            self.setGeometry(compact_rect)
            self._sync_child_geometry()
        self._visualizer.set_mode("success")
        self._hide_after_completion_timer.start(max(120, int(delay_ms)))

    def cancel_processing(self, reason: str = ""):
        self._trace_widget_event(
            "widget_processing_cancelled",
            "AudioVisualizer.cancel_processing",
            reason=reason or "cancel requested",
        )
        self._processing_step_text = ""
        self._visualizer.set_processing_text("")
        self.hide(reason=reason or "processing cancelled")

    def mousePressEvent(self, event):
        self._drag_origin = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is None:
            super().mouseMoveEvent(event)
            return
        delta = event.globalPosition().toPoint() - self._drag_origin
        self.move(self.x() + delta.x(), self.y() + delta.y())
        if self._streaming_answer_active or self._streaming_resize_timer.isActive():
            moved_rect = self.geometry()
            self._streaming_anchor_center_x = int(moved_rect.center().x())
            self._streaming_anchor_bottom_y = int(moved_rect.bottom())
            self._streaming_anchor_valid = True
        self._drag_origin = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)
