from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.database.models import Meeting
from app.main import app


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_health():
    response = client.get("/api/meetings/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_is_lightweight():
    db = TestingSessionLocal()
    db.add(
        Meeting(
            title="Planning",
            date="2026-08-20 10:00:00",
            status="completed",
            transcript_json=[{"text": "long transcript"}],
            result={"summary": "Short summary", "action_items": []},
        )
    )
    db.commit()
    db.close()

    response = client.get("/api/meetings")
    assert response.status_code == 200
    body = response.json()[0]
    assert body["summary_preview"] == "Short summary"
    assert "transcript_json" not in body


def test_upload_returns_202_and_schedules_processing(tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.routes.settings.UPLOAD_DIR", str(tmp_path))
    mock_task = AsyncMock()
    with patch("app.api.routes.meeting_service.process_meeting", mock_task):
        response = client.post(
            "/api/meetings",
            data={"title": "Weekly Sync"},
            files={"file": ("sync.wav", b"fake audio", "audio/wav")},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    mock_task.assert_awaited_once()


def test_invalid_extension_rejected():
    response = client.post(
        "/api/meetings",
        data={"title": "Bad"},
        files={"file": ("payload.exe", b"data", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_get_missing_meeting():
    response = client.get("/api/meetings/9999")
    assert response.status_code == 404


def test_delete_processing_meeting_is_blocked():
    db = TestingSessionLocal()
    meeting = Meeting(title="Busy", date="2026-08-20 10:00:00", status="transcribing")
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    meeting_id = meeting.id
    db.close()

    response = client.delete(f"/api/meetings/{meeting_id}")
    assert response.status_code == 409


def test_retry_requires_existing_audio(tmp_path):
    db = TestingSessionLocal()
    meeting = Meeting(
        title="Failed",
        date="2026-08-20 10:00:00",
        status="failed",
        audio_path=str(tmp_path / "missing.wav"),
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    meeting_id = meeting.id
    db.close()

    response = client.post(f"/api/meetings/{meeting_id}/retry")
    assert response.status_code == 409
