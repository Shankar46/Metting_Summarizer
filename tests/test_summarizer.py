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
        [{"start": 0, "end": 3, "text": "Let's ship on Friday. I will prepare the release."}]
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
async def test_groq_provider_falls_back_to_prompt_json_after_json_object_failure(monkeypatch):
    import openai
    import app.services.llm.provider as provider_module

    calls = []

    class FakeAPIStatusError(Exception):
        def __init__(self, body, status_code=400):
            self.body = body
            self.status_code = status_code

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs.get("response_format"))
            if len(calls) == 1:
                raise FakeAPIStatusError({"error": {"code": "json_validate_failed"}})
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": type("Message", (), {"content": '{"summary":"ok","key_decisions":[],"action_items":[],"open_questions":[]}'} )()})()]},
            )()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(provider_module, "settings", type("Settings", (), {"GROQ_API_KEY": "key", "LLM_MODEL": "test-model", "LLM_MAX_ATTEMPTS": 3, "LLM_MAX_RATE_LIMIT_WAIT_SECONDS": 15})())
    monkeypatch.setattr(provider_module, "asyncio", type("AsyncioStub", (), {"to_thread": staticmethod(lambda fn: fn())})())
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(openai, "APIStatusError", FakeAPIStatusError)
    monkeypatch.setattr(openai, "RateLimitError", type("RateLimitError", (Exception,), {}))

    result = await provider_module.GroqProvider().generate("system", "user", {"type": "object"})
    assert calls == [{"type": "json_object"}, None]
    assert result.startswith("{\"summary\":\"ok\"")


def test_response_normalizes_missing_action_fields_and_ignores_casual_questions():
    normalized = MeetingSummarizer._normalize_response(
        {
            "summary": "A summary.",
            "key_decisions": [],
            "action_items": [{"task": "Follow up on anti-abuse notes", "owner": None}],
            "open_questions": [{"question": "Is there another tea color?"}],
        }
    )

    assert normalized["action_items"] == [
        {
            "task": "Follow up on anti-abuse notes",
            "owner": "Unassigned",
            "deadline": "Not specified",
            "priority": "not_specified",
        }
    ]
    assert normalized["open_questions"] == []


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
        {"start": i, "end": i + 1, "text": "A long sentence that consumes space."}
        for i in range(8)
    ]
    result = await summarizer.summarize(transcript)
    assert result.summary == "A summary."
    assert len(llm.calls) > 1
