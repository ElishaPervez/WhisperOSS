from src.math_formatting import normalize_math_dictation


def test_normalize_math_equation_dictation_sample():
    raw = (
        "x plus 1 whole square plus 5 is equals x square plus 2x plus 6 "
        "by taking x equals to 2,5 and 10."
    )

    assert normalize_math_dictation(raw) == "(x + 1)² + 5 = x² + 2x + 6, taking x = 2, 5 and 10."


def test_normalize_math_non_math_text_unchanged():
    raw = "Please send the report by Friday."
    assert normalize_math_dictation(raw) == raw


def test_normalize_math_handles_the_whole_square_variant():
    raw = "x plus 1 the whole square plus 5"
    assert normalize_math_dictation(raw) == "(x + 1)² + 5"
