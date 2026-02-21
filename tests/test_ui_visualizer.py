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

def test_processing_completion_states(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    vis.set_processing_mode()
    assert vis._visualizer.mode == "processing"

    vis.play_completion_and_hide(delay_ms=150)
    assert vis._visualizer.mode == "success"
    assert vis._hide_after_completion_timer.isActive() is True

def test_animation_fps_updates_timer_interval(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)

    vis.set_animation_fps(100)
    assert vis._visualizer.timer.interval() == 10

def test_hide_does_not_flash_idle_before_fade_complete(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    vis.set_processing_mode()
    assert vis._visualizer.mode == "processing"

    vis.hide()
    # Mode should remain in-flight during fade-out; idle only after fully hidden.
    assert vis._visualizer.mode == "processing"
