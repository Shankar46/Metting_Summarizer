import logging
import os
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.database.models import Meeting
from app.services.asr.base import ASRProvider
from app.services.llm.base import LLMProvider
from app.services.summarizer import MeetingSummarizer

logger = logging.getLogger(__name__)


class MeetingService:
    def __init__(self, asr: ASRProvider, llm: LLMProvider):
        self.asr = asr
        self.summarizer = MeetingSummarizer(llm)

    def create_pending_meeting(self, db: Session, title: str, audio_path: str, duration: float | None) -> Meeting:
        meeting = Meeting(
            title=title,
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="pending",
            duration=duration,
            audio_path=audio_path,
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        return meeting

    async def process_meeting(self, meeting_id: int) -> None:
        """Run the pipeline with a fresh DB session owned by the background task."""
        db = SessionLocal()
        try:
            await self._run_pipeline(db, meeting_id)
        finally:
            db.close()

    async def _run_pipeline(self, db: Session, meeting_id: int) -> None:
        meeting = db.get(Meeting, meeting_id)
        if not meeting:
            logger.error("Meeting %s not found", meeting_id)
            return

        try:
            meeting.status = "transcribing"
            meeting.error_message = None
            db.commit()

            asr_started = time.perf_counter()
            transcript = await self.asr.transcribe(meeting.audio_path or "")
            meeting.asr_seconds = round(time.perf_counter() - asr_started, 3)
            meeting.transcript_json = transcript
            db.commit()

            if not transcript:
                raise ValueError("The transcription service returned no speech segments.")

            meeting.status = "summarizing"
            db.commit()

            summary_started = time.perf_counter()
            result = await self.summarizer.summarize(transcript)
            meeting.summary_seconds = round(time.perf_counter() - summary_started, 3)

            meeting.result = result.model_dump()
            meeting.summary_markdown = self._to_markdown(result.model_dump())
            meeting.status = "completed"
            meeting.error_message = None
            db.commit()
            logger.info("Meeting %s completed", meeting_id)

        except Exception as exc:
            logger.exception("Meeting %s failed", meeting_id)
            db.rollback()
            meeting = db.get(Meeting, meeting_id)
            if meeting:
                meeting.status = "failed"
                meeting.error_message = str(exc)[:2000]
                db.commit()

    @staticmethod
    def _to_markdown(result: dict) -> str:
        lines = ["# Meeting Summary", "", "## Executive Summary", result.get("summary", ""), ""]
        lines.append("## Key Decisions")
        decisions = result.get("key_decisions", [])
        if decisions:
            for item in decisions:
                lines.append(f"- {item.get('description', '')}")
        else:
            lines.append("- None identified")
        lines.extend(["", "## Action Items"])
        actions = result.get("action_items", [])
        if actions:
            lines.append("| Task | Owner | Deadline | Priority |")
            lines.append("|---|---|---|---|")
            for item in actions:
                lines.append(
                    f"| {item.get('task', '')} | {item.get('owner') or 'Unassigned'} | "
                    f"{item.get('deadline') or 'Not specified'} | "
                    f"{item.get('priority', 'not_specified').replace('_', ' ').title()} |"
                )
        else:
            lines.append("- None identified")
        lines.extend(["", "## Open Questions"])
        questions = result.get("open_questions", [])
        if questions:
            for item in questions:
                lines.append(f"- {item.get('question', '')}")
        else:
            lines.append("- None identified")
        return "\n".join(lines)


def get_audio_duration(file_path: str) -> float | None:
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(file_path)
        return round(len(audio) / 1000.0, 2)
    except Exception:
        logger.warning("Could not determine audio duration for %s", file_path)
        return None
