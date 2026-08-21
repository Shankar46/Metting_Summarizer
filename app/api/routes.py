import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.schemas import MeetingListItem, MeetingResponse
from app.core.config import settings
from app.database.database import get_db
from app.database.models import Meeting
from app.services.asr.whisper import WhisperASR
from app.services.llm.provider import get_llm_provider
from app.services.meeting_service import MeetingService, get_audio_duration

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

meeting_service = MeetingService(WhisperASR(), get_llm_provider())
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".mp4", ".mpeg", ".mpga"}
PROCESSING_STATUSES = {"pending", "transcribing", "summarizing"}


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("", response_model=list[MeetingListItem])
def get_meetings(db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.id.desc()).all()
    items = []
    for meeting in meetings:
        result = meeting.result or {}
        items.append(
            MeetingListItem(
                id=meeting.id,
                title=meeting.title,
                date=meeting.date,
                status=meeting.status,
                duration=meeting.duration,
                summary_preview=(meeting.summary_markdown or result.get("summary", ""))[:180] or None,
                action_item_count=len(result.get("action_items", [])),
            )
        )
    return items


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting with ID {meeting_id} not found.")
    return meeting


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_202_ACCEPTED)
@router.post("/upload", response_model=MeetingResponse, status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
async def upload_meeting(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form("New Meeting"),
    db: Session = Depends(get_db),
):
    clean_title = title.strip() or "Untitled Meeting"
    if len(clean_title) > 200:
        raise HTTPException(status_code=400, detail="Meeting title must be 200 characters or fewer.")

    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported audio format: {extension or 'unknown'}.")

    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size <= 0:
        raise HTTPException(status_code=400, detail="The uploaded audio file is empty.")
    if file_size > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB upload limit.",
        )

    filename = f"{uuid.uuid4().hex}{extension}"
    local_path = os.path.join(settings.UPLOAD_DIR, filename)
    try:
        with open(local_path, "wb") as output:
            shutil.copyfileobj(file.file, output, length=1024 * 1024)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to store the uploaded audio file.") from exc
    finally:
        await file.close()

    try:
        duration = get_audio_duration(local_path)
        meeting = meeting_service.create_pending_meeting(db, clean_title, local_path, duration)
    except Exception as exc:
        try:
            os.remove(local_path)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail="Failed to create the meeting record.") from exc

    background_tasks.add_task(meeting_service.process_meeting, meeting.id)
    return meeting


@router.post("/{meeting_id}/retry", response_model=MeetingResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_meeting(meeting_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    if meeting.status in PROCESSING_STATUSES:
        raise HTTPException(status_code=409, detail="Meeting is already being processed.")
    if not meeting.audio_path or not os.path.exists(meeting.audio_path):
        raise HTTPException(status_code=409, detail="Original audio file is no longer available.")

    meeting.status = "pending"
    meeting.error_message = None
    meeting.result = None
    meeting.summary_markdown = None
    meeting.transcript_json = None
    db.commit()
    db.refresh(meeting)
    background_tasks.add_task(meeting_service.process_meeting, meeting.id)
    return meeting


@router.delete("/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    if meeting.status in PROCESSING_STATUSES:
        raise HTTPException(status_code=409, detail="Cannot delete a meeting while it is being processed.")

    if meeting.audio_path:
        try:
            os.remove(meeting.audio_path)
        except FileNotFoundError:
            pass
        except OSError:
            # Keep deletion of the DB record independent from a filesystem cleanup failure.
            pass

    db.delete(meeting)
    db.commit()
    return {"message": "Meeting successfully deleted."}
