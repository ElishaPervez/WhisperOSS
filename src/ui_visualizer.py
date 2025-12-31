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
        
        # Smooth animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)  # ~60 FPS
        
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
        
        # Draw subtle background panel
        bg_gradient = QLinearGradient(0, 0, 0, h)
        bg_gradient.setColorAt(0, QColor(30, 40, 65, 180))
        bg_gradient.setColorAt(1, QColor(20, 28, 50, 200))
        
        painter.setBrush(QBrush(bg_gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.drawRoundedRect(0, 0, w, h, 10, 10)
        
        # Bar configuration
        num_bars = 5
        bar_width = 22
        bar_spacing = 8
        total_bars_width = (num_bars * bar_width) + ((num_bars - 1) * bar_spacing)
        start_x = (w - total_bars_width) / 2
        max_bar_height = h - 16  # Padding
        min_bar_height = 5
        
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
                glow_color = QColor(0, 212, 255, int(60 * glow_intensity))
                painter.setBrush(QBrush(glow_color))
                painter.setPen(Qt.PenStyle.NoPen)
                glow_padding = 3
                painter.drawRoundedRect(
                    int(x - glow_padding), 
                    int(y - glow_padding), 
                    int(bar_width + glow_padding * 2), 
                    int(bar_height + glow_padding * 2), 
                    5, 5
                )
            
            # Main bar gradient (vertical for depth)
            bar_gradient = QLinearGradient(x, y, x, y + bar_height)
            
            # Cyan to blue gradient based on amplitude
            top_color = QColor(0, 230, 255, 255)  # Bright cyan
            mid_color = QColor(0, 180, 220, 255)  # Mid cyan
            bottom_color = QColor(0, 140, 190, 255)  # Deeper blue
            
            bar_gradient.setColorAt(0, top_color)
            bar_gradient.setColorAt(0.5, mid_color)
            bar_gradient.setColorAt(1, bottom_color)
            
            painter.setBrush(QBrush(bar_gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height), 4, 4)
            
            # Highlight on top of bar
            highlight = QLinearGradient(x, y, x, y + bar_height * 0.4)
            highlight.setColorAt(0, QColor(255, 255, 255, 50))
            highlight.setColorAt(1, QColor(255, 255, 255, 0))
            
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
        
        # Smooth animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)  # ~60 FPS
        
    def update_level(self, level):
        """Level is expected to be 0.0 to 1.0"""
        self.target_amplitude = min(1.0, level * 1.5)
        self.is_active = level > 0.01
        
        # Distribute to individual bars with wave-like variation
        for i in range(self.bar_count):
            # Create wave pattern - middle bars higher
            center = self.bar_count / 2
            distance_from_center = abs(i - center) / center
            height_modifier = 1.0 - (distance_from_center * 0.4)
            
            variation = 0.6 + 0.4 * math.sin(self.idle_phase * 2 + self.bar_phases[i])
            self.bar_targets[i] = self.target_amplitude * variation * height_modifier

    def animate(self):
        # Global amplitude lerp
        self.amplitude += (self.target_amplitude - self.amplitude) * 0.15
        
        # Idle animation phase
        self.idle_phase += 0.06
        
        # Individual bar animations
        for i in range(self.bar_count):
            # Add subtle idle movement when not active
            if not self.is_active:
                center = self.bar_count / 2
                distance_from_center = abs(i - center) / center
                height_mod = 1.0 - (distance_from_center * 0.5)
                idle_movement = (0.1 + 0.15 * math.sin(self.idle_phase + self.bar_phases[i])) * height_mod
                self.bar_targets[i] = idle_movement
            
            # Smooth lerp with slight variation per bar
            lerp_speed = 0.1 + 0.02 * (i % 3)
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
        
        for i in range(self.bar_count):
            amp = self.bar_amplitudes[i]
            bar_height = min_bar_height + (max_bar_height - min_bar_height) * amp
            bar_height = max(min_bar_height, min(max_bar_height, bar_height))
            
            x = start_x + i * (bar_width + bar_spacing)
            y = (h - bar_height) / 2
            
            # Glow effect when active
            glow_intensity = amp * 0.7
            if glow_intensity > 0.1:
                glow_color = QColor(255, 255, 255, int(40 * glow_intensity))  # White glow
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
            painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height), 2, 2)


# Keep AudioVisualizer for backward compatibility if needed as overlay
class AudioVisualizer(QWidget):
    """Floating audio visualizer overlay with compact bar design and fade animation"""
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
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
        
    def _animate_fade(self):
        """Smooth fade animation step."""
        diff = self._fade_target - self._opacity
        if abs(diff) < 0.02:
            self._opacity = self._fade_target
            self._fade_timer.stop()
            if self._opacity <= 0:
                super().hide()
        else:
            self._opacity += diff * 0.15  # Smooth lerp
        self.setWindowOpacity(self._opacity)
        
    def show(self):
        """Show with fade in animation."""
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
        self._is_showing = False
        self._fade_target = 0.0
        if not self._fade_timer.isActive():
            self._fade_timer.start(16)
        
    def update_level(self, level):
        self._visualizer.update_level(level)

    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = event.globalPosition().toPoint() - self.oldPos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()
