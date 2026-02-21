from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient, QRadialGradient
import math


class EmbeddedAudioVisualizer(QWidget):
    """Embedded audio visualizer for integration into main window layout"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setMinimumWidth(180)

        # Visual state
        self.amplitude = 0.0
        self.target_amplitude = 0.0

        # Individual bar states for more organic movement
        self.bar_amplitudes = [0.0] * 5
        self.bar_targets = [0.0] * 5
        self.bar_phases = [i * 0.5 for i in range(5)]  # Offset phases for wave effect

        # Animation phase for idle animation
        self.idle_phase = 0.0
        self.is_active = False

        # Cache graphical objects
        self._init_graphics()

        # Smooth animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)  # ~60 FPS

    def _init_graphics(self):
        """Initialize cached graphics objects to reduce paintEvent load."""
        # Colors
        self.col_transparent = QColor(0, 0, 0, 0)
        self.col_border = QColor(255, 255, 255, 20)
        self.col_glow = QColor(0, 212, 255) # Base glow color
        self.col_bar_top = QColor(0, 230, 255, 255)
        self.col_bar_mid = QColor(0, 180, 220, 255)
        self.col_bar_bot = QColor(0, 140, 190, 255)
        self.col_highlight_start = QColor(255, 255, 255, 50)
        self.col_highlight_end = QColor(255, 255, 255, 0)

        # Pens
        self.pen_border = QPen(self.col_border, 1)
        self.pen_none = Qt.PenStyle.NoPen

        # Background gradient (recreated on resize)
        self.brush_bg = None
        self._update_bg_gradient()

    def resizeEvent(self, event):
        self._update_bg_gradient()
        super().resizeEvent(event)

    def _update_bg_gradient(self):
        h = self.height()
        bg_gradient = QLinearGradient(0, 0, 0, h)
        bg_gradient.setColorAt(0, QColor(30, 40, 65, 180))
        bg_gradient.setColorAt(1, QColor(20, 28, 50, 200))
        self.brush_bg = QBrush(bg_gradient)

    def update_level(self, level):
        """Level is expected to be 0.0 to 1.0"""
        self.target_amplitude = min(1.0, level * 1.5)  # Slight boost for visibility
        self.is_active = level > 0.01

        # Distribute to individual bars with slight variation
        for i in range(5):
            variation = 0.7 + 0.6 * math.sin(self.idle_phase + self.bar_phases[i])
            self.bar_targets[i] = self.target_amplitude * variation

    def animate(self):
        # Global amplitude lerp
        self.amplitude += (self.target_amplitude - self.amplitude) * 0.15

        # Idle animation phase
        self.idle_phase += 0.08

        # Individual bar animations with different speeds
        for i in range(5):
            # Add subtle idle movement
            if not self.is_active:
                idle_movement = 0.15 + 0.1 * math.sin(self.idle_phase + self.bar_phases[i] * 2)
                self.bar_targets[i] = idle_movement

            # Smooth lerp with slight variation per bar
            lerp_speed = 0.12 + 0.03 * i
            self.bar_amplitudes[i] += (self.bar_targets[i] - self.bar_amplitudes[i]) * lerp_speed

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Draw subtle background panel using cached brush
        if self.brush_bg:
            painter.setBrush(self.brush_bg)
        painter.setPen(self.pen_border)
        painter.drawRoundedRect(0, 0, w, h, 10, 10)

        # Bar configuration
        num_bars = 5
        bar_width = 22
        bar_spacing = 8
        total_bars_width = (num_bars * bar_width) + ((num_bars - 1) * bar_spacing)
        start_x = (w - total_bars_width) / 2
        max_bar_height = h - 16  # Padding
        min_bar_height = 5

        painter.setPen(self.pen_none)

        for i in range(num_bars):
            # Calculate bar height with wave-like variation
            amp = self.bar_amplitudes[i]

            # Middle bars slightly taller for aesthetic
            height_modifier = 1.0 - (abs(2 - i) * 0.12)
            bar_height = min_bar_height + (max_bar_height - min_bar_height) * amp * height_modifier
            bar_height = max(min_bar_height, min(max_bar_height, bar_height))

            x = start_x + i * (bar_width + bar_spacing)
            y = (h - bar_height) / 2

            # Glow effect (larger, more transparent behind)
            glow_intensity = amp * 0.6
            if glow_intensity > 0.05:
                # Modifying alpha of cached color
                self.col_glow.setAlpha(int(60 * glow_intensity))
                painter.setBrush(QBrush(self.col_glow))
                glow_padding = 3
                painter.drawRoundedRect(
                    int(x - glow_padding),
                    int(y - glow_padding),
                    int(bar_width + glow_padding * 2),
                    int(bar_height + glow_padding * 2),
                    5, 5
                )

            # Main bar gradient (vertical for depth)
            # Gradients dependent on dynamic height must be created here
            bar_gradient = QLinearGradient(x, y, x, y + bar_height)
            bar_gradient.setColorAt(0, self.col_bar_top)
            bar_gradient.setColorAt(0.5, self.col_bar_mid)
            bar_gradient.setColorAt(1, self.col_bar_bot)

            painter.setBrush(QBrush(bar_gradient))
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height), 4, 4)

            # Highlight on top of bar
            highlight = QLinearGradient(x, y, x, y + bar_height * 0.4)
            highlight.setColorAt(0, self.col_highlight_start)
            highlight.setColorAt(1, self.col_highlight_end)

            painter.setBrush(QBrush(highlight))
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height * 0.4), 4, 4)


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
        self.mode = "idle"  # idle | listening | processing | completing
        self.processing_phase = 0.0
        self.completion_progress = 0.0
        self.processing_mix = 0.0  # 0=bars only, 1=loader only
        
        # Smooth animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)  # ~60 FPS

    def set_mode(self, mode: str):
        """Switch animation mode for recording lifecycle transitions."""
        if mode not in {"idle", "listening", "processing", "completing"}:
            return

        previous_mode = self.mode
        self.mode = mode
        if mode == "idle":
            self.target_amplitude = 0.0
            self.is_active = False
            self.processing_mix = 0.0
        elif mode == "listening":
            self.is_active = False
            self.processing_mix = 0.0
        elif mode == "processing":
            self.processing_phase = 0.0
            self.target_amplitude = 0.42
            self.is_active = True
            # Keep a tiny blend if we were already in processing, otherwise
            # restart transition from bars -> loader.
            self.processing_mix = 0.0 if previous_mode != "processing" else min(self.processing_mix, 0.3)
        elif mode == "completing":
            self.completion_progress = 0.0
            self.target_amplitude = 0.0
            self.is_active = True
            self.processing_mix = 1.0
        
    def update_level(self, level):
        """Level is expected to be 0.0 to 1.0"""
        if self.mode in {"processing", "completing"}:
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
            self.processing_phase += 0.11
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

        if self.mode == "completing":
            # Keep motion alive during completion so the loader never appears frozen.
            self.processing_phase += 0.09
            self.completion_progress = min(1.0, self.completion_progress + 0.07)
            if self.completion_progress < 0.45:
                envelope = self.completion_progress / 0.45
            else:
                envelope = max(0.0, 1.0 - (self.completion_progress - 0.45) / 0.55)

            for i in range(self.bar_count):
                distance = abs(i - center) / max(center, 1.0)
                peak = (1.0 - distance * 0.65)
                self.bar_targets[i] = max(0.0, envelope * peak)
                self.bar_amplitudes[i] += (self.bar_targets[i] - self.bar_amplitudes[i]) * 0.26

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
        
        # Draw dark translucent background pill
        bg_gradient = QLinearGradient(0, 0, 0, h)
        bg_gradient.setColorAt(0, QColor(0, 0, 0, 150))
        bg_gradient.setColorAt(1, QColor(0, 0, 0, 180))
        
        painter.setBrush(QBrush(bg_gradient))
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

        # Distinct processing loader: dotted runner + rotating spinner.
        loader_alpha = self.processing_mix
        if self.mode == "completing":
            # Fade loader out during completion instead of holding a static full-opacity state.
            loader_alpha *= max(0.0, 1.0 - self.completion_progress)
        if loader_alpha > 0.01:
            line_left = 18
            spinner_cx = w - 16
            line_right = max(line_left + 12, spinner_cx - 10)
            line_y = h / 2
            dot_spacing = 6
            dot_radius = 1.1
            dot_count = max(3, int((line_right - line_left) / dot_spacing))

            for idx in range(dot_count):
                x = line_left + idx * dot_spacing
                if x >= line_right:
                    break
                phase = self.processing_phase * 1.1 - idx * 0.55
                pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(phase))
                dot_alpha = int(180 * loader_alpha * pulse)
                painter.setBrush(QBrush(QColor(255, 255, 255, dot_alpha)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(int(x - dot_radius), int(line_y - dot_radius), int(dot_radius * 2.2), int(dot_radius * 2.2))

            spinner_cy = h / 2
            spinner_radius = 5.8
            spoke_len = 2.6
            spokes = 8
            rotation = self.processing_phase * 1.35
            for spoke in range(spokes):
                angle = rotation + (2 * math.pi * spoke / spokes)
                x1 = spinner_cx + math.cos(angle) * (spinner_radius - spoke_len)
                y1 = spinner_cy + math.sin(angle) * (spinner_radius - spoke_len)
                x2 = spinner_cx + math.cos(angle) * spinner_radius
                y2 = spinner_cy + math.sin(angle) * spinner_radius
                tail = (spokes - spoke) / spokes
                alpha = int(255 * loader_alpha * (0.25 + 0.75 * tail))
                painter.setPen(QPen(QColor(255, 255, 255, alpha), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))


# Keep AudioVisualizer for backward compatibility if needed as overlay
class AudioVisualizer(QWidget):
    """Floating audio visualizer overlay with compact bar design and fade animation"""
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput  # Click-through: allows clicking elements behind
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(120, 36)  # Compact size
        
        # Create compact visualizer as child
        self._visualizer = CompactAudioVisualizer(self)
        self._visualizer.setFixedSize(120, 36)
        
        # Fade animation setup
        self._opacity = 0.0
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._animate_fade)
        self._fade_target = 0.0
        self._is_showing = False

        self._hide_after_completion_timer = QTimer(self)
        self._hide_after_completion_timer.setSingleShot(True)
        self._hide_after_completion_timer.timeout.connect(self.hide)
        
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
            self._opacity += diff * 0.15  # Smooth lerp
        self.setWindowOpacity(self._opacity)
        
    def show(self):
        """Show with fade in animation."""
        self._hide_after_completion_timer.stop()
        if not self._is_showing:
            self._is_showing = True
            self._opacity = 0.0
            self.setWindowOpacity(0.0)
            super().show()
        self._fade_target = 1.0
        if not self._fade_timer.isActive():
            self._fade_timer.start(16)  # ~60fps
    
    def hide(self):
        """Hide with fade out animation."""
        self._hide_after_completion_timer.stop()
        self._is_showing = False
        self._fade_target = 0.0
        if not self._fade_timer.isActive():
            self._fade_timer.start(16)

    def update_level(self, level):
        self._visualizer.update_level(level)

    def set_listening_mode(self):
        self._hide_after_completion_timer.stop()
        self._visualizer.set_mode("listening")

    def set_processing_mode(self):
        self._hide_after_completion_timer.stop()
        self._visualizer.set_mode("processing")

    def play_completion_and_hide(self, delay_ms: int = 260):
        self._visualizer.set_mode("completing")
        self._hide_after_completion_timer.start(max(120, int(delay_ms)))

    def cancel_processing(self):
        self.hide()

    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = event.globalPosition().toPoint() - self.oldPos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()
