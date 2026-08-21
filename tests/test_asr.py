from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import sys
import types

import pytest

from app.services.asr.whisper import WhisperASR


@pytest.mark.asyncio
@patch("app.services.asr.whisper.settings")
async def test_mock_asr_does_not_fabricate_speakers(mock_settings):
    mock_settings.ASR_PROVIDER = "mock"
    segments = await WhisperASR().transcribe("unused.wav")
    assert segments[0]["speaker"] is None


@pytest.mark.asyncio
@patch("app.services.asr.whisper.settings")
async def test_api_segments_are_normalized(mock_settings):
    mock_settings.ASR_PROVIDER = "groq_whisper"
    mock_settings.GROQ_API_KEY = "test-key"
    mock_settings.GROQ_BASE_URL = "https://api.groq.com/openai/v1"
    mock_settings.ASR_MODEL = "whisper-large-v3"
    mock_settings.ASR_LANGUAGE = None

    response = SimpleNamespace(
        segments=[SimpleNamespace(start=1.25, end=3.5, text=" Hello there ", speaker=None)]
    )
    client = MagicMock()
    client.audio.transcriptions.create.return_value = response

    fake_openai = types.SimpleNamespace(OpenAI=MagicMock(return_value=client))
    with patch.dict(sys.modules, {"openai": fake_openai}), patch("builtins.open", MagicMock()):
        result = await WhisperASR()._api_transcribe("audio.wav")

    assert result == [{"start": 1.25, "end": 3.5, "text": "Hello there", "speaker": None}]
