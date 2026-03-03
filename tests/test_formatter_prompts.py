from src import prompts


def test_formatter_styles_only_include_default():
    assert prompts.FORMATTING_STYLES == ["Default"]


def test_get_formatter_prompt_ignores_non_default_style():
    assert prompts.get_formatter_prompt("Email") == prompts.SYSTEM_PROMPT_DEFAULT


def test_default_prompt_mentions_math_normalization_rules():
    prompt = prompts.SYSTEM_PROMPT_DEFAULT
    assert "MATH NORMALIZATION" in prompt
    assert "x plus 1 whole square" in prompt


def test_default_prompt_mentions_whole_square_variants():
    prompt = prompts.SYSTEM_PROMPT_DEFAULT.lower()
    assert "the whole square" in prompt
    assert "all square" in prompt
