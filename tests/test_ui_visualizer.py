import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.ui_visualizer import AudioVisualizer, CompactAudioVisualizer

@pytest.fixture
def app(qtbot):
    return QApplication.instance() or QApplication([])

def test_compact_visualizer_init(app, qtbot):
    vis = CompactAudioVisualizer()
    qtbot.addWidget(vis)
    assert vis.amplitude == 0.0
    
    # Test update
    vis.update_level(1.0)
    assert vis.target_amplitude > 0.0

def test_legacy_visualizer_init(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    assert vis.windowFlags() & Qt.WindowType.FramelessWindowHint
    
    # Test update delegates to embedded
    vis.update_level(0.5)
    # Corrected attribute name
    assert vis._visualizer.target_amplitude > 0.0

def test_fade_animation(app, qtbot):
    vis = AudioVisualizer()
    vis.show()
    assert vis._is_showing is True
    assert vis._fade_target == 1.0
    
    vis.hide()
    assert vis._is_showing is False
    assert vis._fade_target == 0.0