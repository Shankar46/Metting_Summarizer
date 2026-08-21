import json

import pytest

from app.api.schemas import MeetingResult
from app.services.llm.base import LLMProvider
from app.services.summarizer import MeetingSummarizer


class MockLLM(LLMProvider):
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def generate(self, system_prompt, user_prompt, response_schema):
        self.calls.append((system_prompt, user_prompt, response_schema))
        return json.dumps(self.payload)


@pytest.mark.asyncio
async def test_summarizer_returns_validated_result():
    llm = MockLLM(
        {
            "summary": "The team agreed to ship on Friday.",
            "key_decisions": [{"description": "Ship on Friday.", "evidence": None}],
            "action_items": [
                {
                    "task": "Prepare release",
                    "owner": "Asha",
                    "deadline": "Friday",
                    "priority": "high",
                    "evidence": None,
                }
            ],
            "open_questions": [],
        }
    )
    summarizer = MeetingSummarizer(llm)
    result = await summarizer.summarize(
        [{"speaker": "Asha", "start": 0, "end": 3, "text": "Let's ship on Friday. I will prepare the release."}]
    )

    assert isinstance(result, MeetingResult)
    assert result.action_items[0].owner == "Asha"
    assert "ship on friday" in llm.calls[0][1].lower()
    assert llm.calls[0][2]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_empty_transcript_is_rejected():
    summarizer = MeetingSummarizer(MockLLM({}))
    with pytest.raises(ValueError, match="empty transcript"):
        await summarizer.summarize([])


@pytest.mark.asyncio
async def test_long_transcript_is_chunked(monkeypatch):
    monkeypatch.setattr("app.services.summarizer.settings.TRANSCRIPT_CHUNK_CHARS", 100)
    payload = {
        "summary": "A summary.",
        "key_decisions": [],
        "action_items": [],
        "open_questions": [],
    }
    llm = MockLLM(payload)
    summarizer = MeetingSummarizer(llm)
    transcript = [
        {"speaker": "A", "start": i, "end": i + 1, "text": "A long sentence that consumes space."}
        for i in range(8)
    ]
    result = await summarizer.summarize(transcript)
    assert result.summary == "A summary."
    assert len(llm.calls) > 1
