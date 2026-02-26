from typing import Iterable

from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap


class ScreenRegionSelector(QDialog):
    """Modal crosshair overlay to select a screen region and return a cropped pixmap."""

    def __init__(self, screens: Iterable, preferred_screen=None, parent=None):
        super().__init__(parent)
        self._screens = [s for s in screens if s is not None]
        if not self._screens and preferred_screen is not None:
            self._screens = [preferred_screen]
        if not self._screens:
            raise ValueError("ScreenRegionSelector requires at least one screen.")

        self._screen_geometry = self._build_virtual_geometry(self._screens)
        self._background = self._build_virtual_background(self._screens, self._screen_geometry)
        self._start_pos = None
        self._end_pos = None
        self._selection_rect = QRect()
        self._captured = QPixmap()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setGeometry(self._screen_geometry)

    @staticmethod
    def _build_virtual_geometry(screens) -> QRect:
        virtual = QRect(screens[0].geometry())
        for screen in screens[1:]:
            virtual = virtual.united(screen.geometry())
        return virtual

    @staticmethod
    def _build_virtual_background(screens, virtual_geometry: QRect) -> QPixmap:
        background = QPixmap(virtual_geometry.size())
        background.fill(QColor(0, 0, 0))

        painter = QPainter(background)
        for screen in screens:
            shot = screen.grabWindow(0)
            if shot.isNull():
                continue
            geo = screen.geometry()
            target = QRect(
                geo.x() - virtual_geometry.x(),
                geo.y() - virtual_geometry.y(),
                geo.width(),
                geo.height(),
            )
            painter.drawPixmap(target, shot)
        painter.end()
        return background

    def _current_rect(self) -> QRect:
        if self._start_pos is None or self._end_pos is None:
            return QRect()
        return QRect(self._start_pos, self._end_pos).normalized().intersected(self.rect())

    def selected_pixmap(self) -> QPixmap:
        return self._captured

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._start_pos = event.position().toPoint()
        self._end_pos = self._start_pos
        self._selection_rect = QRect()
        self.update()

    def mouseMoveEvent(self, event):
        if self._start_pos is None:
            super().mouseMoveEvent(event)
            return
        self._end_pos = event.position().toPoint()
        self._selection_rect = self._current_rect()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._start_pos is None:
            super().mouseReleaseEvent(event)
            return

        self._end_pos = event.position().toPoint()
        self._selection_rect = self._current_rect()
        if self._selection_rect.width() < 6 or self._selection_rect.height() < 6:
            self.reject()
            return

        self._captured = self._background.copy(self._selection_rect)
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == int(Qt.Key.Key_Escape):
            self.reject()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(0, 0, self._background)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 124))

        active_rect = self._selection_rect if not self._selection_rect.isNull() else self._current_rect()
        if not active_rect.isNull() and active_rect.width() > 0 and active_rect.height() > 0:
            painter.drawPixmap(active_rect, self._background, active_rect)
            painter.setPen(QPen(QColor(255, 255, 255, 232), 1))
            painter.drawRect(active_rect.adjusted(0, 0, -1, -1))
            painter.setPen(QPen(QColor(0, 0, 0, 180), 1))
            painter.drawRect(active_rect.adjusted(1, 1, -2, -2))
