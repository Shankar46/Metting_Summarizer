from app.prompts.meeting_prompt import get_summarizer_system_prompt


def test_prompt_has_grounding_rules():
    prompt = get_summarizer_system_prompt().lower()
    assert "never invent" in prompt
    assert "actual decision or agreement" in prompt
    assert "deadline" in prompt
    assert '"not_specified"' in prompt
