import pytest
from app.services.summarizer import MeetingSummarizer
from app.services.llm.base import LLMProvider

# Create a minimal subclass or mock provider for initializing MeetingSummarizer
class DummyLLM(LLMProvider):
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        return ""

@pytest.fixture
def summarizer():
    return MeetingSummarizer(DummyLLM())

def test_parse_clean_json(summarizer):
    raw = '{"summary": "Test", "key_decisions": [], "action_items": [], "open_questions": []}'
    parsed = summarizer._parse_json_response(raw)
    assert parsed["summary"] == "Test"

def test_parse_json_with_markdown_blocks(summarizer):
    raw = '```json\n{"summary": "Markdown Test", "key_decisions": [], "action_items": [], "open_questions": []}\n```'
    parsed = summarizer._parse_json_response(raw)
    assert parsed["summary"] == "Markdown Test"

def test_parse_json_with_surrounding_text_noise(summarizer):
    raw = 'Here is the result:\n{\n  "summary": "Noisy Test",\n  "key_decisions": [],\n  "action_items": [],\n  "open_questions": []\n}\nHope this helps!'
    parsed = summarizer._parse_json_response(raw)
    assert parsed["summary"] == "Noisy Test"

def test_parse_malformed_json_raises_value_error(summarizer):
    raw = '{"summary": "No ending brace"'
    with pytest.raises(ValueError) as exc_info:
        summarizer._parse_json_response(raw)
    assert "Failed to parse LLM response as JSON" in str(exc_info.value)
