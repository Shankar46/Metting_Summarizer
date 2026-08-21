import pytest

from app.api.schemas import MeetingResult
from app.database.database import Base
from app.database.models import Meeting
from app.services.meeting_service import MeetingService


class FakeASR:
    async def transcribe(self, audio_path):
        return [{"start": 0.0, "end": 2.0, "text": "We will ship Friday."}]


class FakeLLM:
    async def generate(self, system_prompt, user_prompt, response_schema):
        return MeetingResult(
            summary="The team will ship Friday.",
            key_decisions=[{"description": "Ship Friday.", "evidence": None}],
            action_items=[],
            open_questions=[],
        ).model_dump_json()


@pytest.mark.asyncio
async def test_pipeline_marks_completed(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    audio = tmp_path / "meeting.wav"
    audio.write_bytes(b"audio")
    meeting = Meeting(title="Test", date="2026-08-20 10:00:00", status="pending", audio_path=str(audio))
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    service = MeetingService(FakeASR(), FakeLLM())
    # Avoid depending on pydub in this unit test.
    await service._run_pipeline(db, meeting.id)
    db.refresh(meeting)

    assert meeting.status == "completed"
    assert meeting.result["key_decisions"][0]["description"] == "Ship Friday."
    assert meeting.error_message is None
    db.close()
