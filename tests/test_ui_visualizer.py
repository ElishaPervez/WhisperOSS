import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QRect
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

def test_processing_step_text_expands_compact_width(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    vis.set_processing_mode("Processing")
    baseline_width = vis.width()
    vis.set_processing_step("Searching Reddit threads for this exact explorer.exe class-not-registered fix")
    qtbot.wait(180)

    assert vis.width() >= baseline_width
    assert vis.width() > vis.COMPACT_WIDTH
    assert vis.width() <= vis.PROCESSING_MAX_WIDTH
    assert vis._visualizer.processing_text.startswith("Searching Reddit")

def test_processing_step_short_text_keeps_compact_min_width(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    vis.set_processing_mode("Thinking")
    qtbot.wait(160)

    assert vis.width() >= vis.COMPACT_WIDTH

def test_listening_mode_resets_compact_geometry_after_processing(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    vis.set_processing_mode("Searching Reddit threads for this exact explorer.exe class-not-registered fix")
    qtbot.wait(180)
    assert vis.width() > vis.COMPACT_WIDTH

    vis.set_listening_mode()
    qtbot.wait(100)

    assert vis.width() == vis.COMPACT_WIDTH
    assert vis.height() == vis.COMPACT_HEIGHT

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


def test_markdown_answer_normalizes_malformed_bold_spacing(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    answer = "These are ** Hina Choso ** and ** Chinatsu Kano** from Blue Box."
    vis.show_answer(answer)
    qtbot.wait(620)

    assert vis._answer_visible is True
    assert vis._answer_label.text() == "These are **Hina Choso** and **Chinatsu Kano** from Blue Box."


def test_streaming_answer_auto_dismiss_starts_only_after_completion(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()
    vis.set_processing_mode("Sending API request")

    vis.begin_streaming_answer()
    vis.update_streaming_answer("Hello")
    qtbot.wait(140)
    assert vis._answer_visible is True
    assert vis._auto_dismiss_timer.isActive() is False

    vis.complete_streaming_answer("Hello world")
    qtbot.wait(1700)
    assert vis._auto_dismiss_timer.isActive() is True
    assert vis._answer_label.text() == "Hello world"


def test_streaming_answer_normalizes_malformed_bold_spacing(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()
    vis.set_processing_mode("Sending API request")

    vis.begin_streaming_answer()
    vis.update_streaming_answer("These are ** Hina Choso ** and ** Chinatsu Kano**.")
    vis.complete_streaming_answer("These are ** Hina Choso ** and ** Chinatsu Kano**.")
    qtbot.wait(3600)

    assert vis._answer_label.text() == "These are **Hina Choso** and **Chinatsu Kano**."


def test_streaming_answer_dismiss_ignores_future_updates(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()
    vis.set_processing_mode("Sending API request")

    vis.begin_streaming_answer()
    vis.update_streaming_answer("First")
    qtbot.wait(120)
    vis.dismiss_answer(reason="user dismissed stream")
    qtbot.wait(120)
    assert vis._streaming_answer_dismissed is True

    vis.update_streaming_answer("Should not re-open")
    qtbot.wait(80)
    assert vis._answer_visible is False


def test_streaming_answer_reveals_progressively_before_completion(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()
    vis.set_processing_mode("Sending API request")

    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    vis.begin_streaming_answer()
    vis.update_streaming_answer(text)
    qtbot.wait(700)

    # Streaming text should reveal progressively, not jump to the final text.
    assert vis._answer_label.text() != text
    assert len(vis._answer_label.text().strip()) > 0

    vis.complete_streaming_answer(text)
    qtbot.wait(1700)
    assert vis._answer_label.text() == text
    assert vis._auto_dismiss_timer.isActive() is True


def test_streaming_answer_growth_keeps_center_anchor(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()
    vis._screen_geometry_for_rect = lambda _: QRect(0, 0, 2400, 1400)
    # Keep initial anchor away from clamp edges so drift checks are meaningful.
    vis.move(1100, 360)
    vis.set_processing_mode("Sending API request")

    vis.begin_streaming_answer()
    vis.update_streaming_answer("alpha beta gamma delta")
    qtbot.wait(260)
    anchor_center = vis.geometry().center().x()

    vis.update_streaming_answer(" ".join(["word"] * 140))
    qtbot.wait(650)
    mid_center = vis.geometry().center().x()

    vis.update_streaming_answer(" ".join(["word"] * 260))
    qtbot.wait(650)
    late_center = vis.geometry().center().x()

    assert abs(mid_center - anchor_center) <= 2
    assert abs(late_center - anchor_center) <= 2


def test_answer_card_caps_to_viewport_and_scrolls_for_long_content(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    vis._screen_geometry_for_rect = lambda _: QRect(0, 0, 1000, 800)
    answer = ("Long content " * 500).strip()
    vis.show_answer(answer)
    qtbot.wait(800)

    assert vis.width() <= 900
    assert vis.height() <= 560
    assert vis._answer_scroll.verticalScrollBar().maximum() > 0


def test_answer_card_markdown_lists_do_not_clip_and_scroll(app, qtbot):
    vis = AudioVisualizer()
    qtbot.addWidget(vis)
    vis.show()

    vis._screen_geometry_for_rect = lambda _: QRect(0, 0, 1200, 600)
    repeated = "".join(
        f"* **Extra Line {idx}:** Added intentionally so the card must become scrollable with markdown lists and wrapped text.\n"
        for idx in range(1, 18)
    )
    answer = (
        "This is an English **pangram** used for keyboard and font testing.\n\n"
        "* **Earliest Appearance:** The phrase appeared in newspaper examples.\n"
        "* **Historical Milestone:** It was used in telecom testing lines.\n"
        "* **Modern Usage:** Designers use it to compare typefaces quickly.\n"
        "* **Practical Value:** It exposes spacing and glyph issues fast.\n"
        "* **Readability Check:** It helps validate punctuation and numerals.\n"
        f"{repeated}"
    )
    vis.show_answer(answer)
    qtbot.wait(900)

    scroll_bar = vis._answer_scroll.verticalScrollBar()
    assert scroll_bar.maximum() > 0
    assert vis._answer_body_container.height() > vis._answer_scroll.viewport().height()
