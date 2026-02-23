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

def test_show_answer_switches_to_interactive_card(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    vis.show_answer("Paris is the capital of France.")
    qtbot.wait(180)

    assert vis._answer_visible is True
    assert vis._answer_card.isVisible() is True
    assert vis._click_through is False
    assert not bool(vis.windowFlags() & Qt.WindowType.WindowTransparentForInput)
    assert vis._auto_dismiss_timer.isActive() is True
    assert vis._auto_dismiss_timer.interval() == vis.ANSWER_AUTO_DISMISS_MS

def test_answer_card_compacts_for_short_answers(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    vis.show_answer("Paris is the capital of Pakistan.")
    qtbot.wait(620)

    assert vis.width() < 340
    assert vis.height() < 116

def test_dismiss_answer_resets_compact_widget(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()
    vis.show_answer("Paris")
    qtbot.wait(220)

    vis.dismiss_answer()
    qtbot.wait(300)

    assert vis._answer_visible is False
    assert vis._answer_card.isVisible() is False
    assert vis._click_through is True
    assert vis._visualizer.mode == "success"
    assert vis.width() == vis.COMPACT_WIDTH
    assert vis.height() == vis.COMPACT_HEIGHT
    assert vis._hide_after_completion_timer.isActive() is True

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

def test_answer_transition_duration_scales_with_fps(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)

    vis.set_animation_fps(60)
    slow = vis._duration_for_frames(20)
    vis.set_animation_fps(180)
    fast = vis._duration_for_frames(20)

    assert fast < slow

def test_hide_does_not_flash_idle_before_fade_complete(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    vis.set_processing_mode()
    assert vis._visualizer.mode == "processing"

    vis.hide()
    # Mode should remain in-flight during fade-out; idle only after fully hidden.
    assert vis._visualizer.mode == "processing"


def test_measure_wrapped_text_tracks_narrow_width_growth(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)

    text = (
        "This is verse 152 of Surah Al-Baqarah from the Quran, which translates to: "
        "So remember Me; I will remember you. And be grateful to Me and do not deny Me."
    )
    wide_height, wide_lines = vis._measure_wrapped_text(text, 420)
    narrow_height, narrow_lines = vis._measure_wrapped_text(text, 190)

    assert narrow_lines > wide_lines
    assert narrow_height > wide_height


def test_multiline_answer_card_expands_for_long_content(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    answer = (
        "This is verse 152 of Surah Al-Baqarah from the Quran, which translates to:\n\n"
        "So remember Me; I will remember you. And be grateful to Me and do not deny Me."
    )
    vis.show_answer(answer)
    qtbot.wait(620)

    assert vis._answer_visible is True
    assert vis._answer_label.text() == answer
    assert vis.height() > vis.CARD_MIN_HEIGHT


def test_markdown_answer_renders_in_markdown_mode(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    answer = (
        "**Meaning**\n"
        "* Remember Me\n"
        "* I will remember you\n"
        "* Be grateful"
    )
    vis.show_answer(answer)
    qtbot.wait(620)

    assert vis._answer_visible is True
    assert vis._answer_label.textFormat() == Qt.TextFormat.MarkdownText
    assert vis._answer_label.text() == answer
