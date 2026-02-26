from src import prompts


def test_search_prompt_has_case_routing_and_specialized_rule():
    prompt = prompts.SYSTEM_PROMPT_SEARCH
    assert "CASE ROUTING (MANDATORY)" in prompt
    assert "Search Reddit first" in prompt
    assert "TRANSLATION REQUEST" in prompt
    assert "Do NOT search" in prompt
    assert "NO GENERIC SOLUTIONS" in prompt
    assert "specialized" in prompt.lower()


def test_search_image_prompt_has_case_routing_and_specialized_rule():
    prompt = prompts.SYSTEM_PROMPT_SEARCH_IMAGE
    assert "CASE ROUTING (MANDATORY)" in prompt
    assert "Search Reddit first" in prompt
    assert "TRANSLATION REQUEST" in prompt
    assert "Do NOT search" in prompt
    assert "NO GENERIC SOLUTIONS" in prompt
    assert "specialized" in prompt.lower()
