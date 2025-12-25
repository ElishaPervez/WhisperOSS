import pytest
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QMouseEvent
from src.ui_visualizer import AudioVisualizer, EmbeddedAudioVisualizer

@pytest.fixture
def app(qtbot):
    return QApplication.instance() or QApplication([])

def test_embedded_visualizer_init(app, qtbot):
    vis = EmbeddedAudioVisualizer()
    qtbot.addWidget(vis)
    assert vis.amplitude == 0.0
    assert not vis.is_active

def test_embedded_visualizer_update(app, qtbot):
    vis = EmbeddedAudioVisualizer()
    qtbot.addWidget(vis)
    
    vis.update_level(0.8)
    assert vis.target_amplitude > 0.0
    assert vis.is_active
    
    vis.update_level(0.0)
    assert vis.target_amplitude == 0.0
    assert not vis.is_active

def test_embedded_visualizer_animate(app, qtbot):
    vis = EmbeddedAudioVisualizer()
    qtbot.addWidget(vis)
    
    vis.update_level(0.5)
    initial_amp = vis.amplitude
    vis.animate()
    assert vis.amplitude > initial_amp
    assert vis.idle_phase > 0.0

def test_embedded_visualizer_paint(app, qtbot):
    vis = EmbeddedAudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()
    vis.update_level(0.5)
    vis.animate()
    # Trigger paintEvent
    vis.repaint()
    
    # Test high amplitude for glow
    vis.update_level(1.0)
    vis.animate()
    vis.repaint()

def test_legacy_visualizer_init(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    assert vis.windowFlags() & Qt.WindowType.FramelessWindowHint
    
    vis.update_level(0.5)
    assert vis._embedded.target_amplitude > 0.0

def test_legacy_visualizer_mouse_move(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()
    
    initial_pos = vis.pos()
    
    # Simulate mouse press
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(vis.x() + 10, vis.y() + 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    vis.mousePressEvent(press_event)
    
    # Simulate mouse move
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(20, 20),
        QPointF(vis.x() + 20, vis.y() + 20),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    vis.mouseMoveEvent(move_event)
    
    assert vis.pos() != initial_pos

def test_embedded_visualizer_idle_animation(app, qtbot):
    vis = EmbeddedAudioVisualizer()
    qtbot.addWidget(vis)
    vis.is_active = False
    vis.animate()
    assert vis.bar_targets[0] > 0
