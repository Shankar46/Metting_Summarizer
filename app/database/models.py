from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    transcript_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary_markdown: Mapped[str | None] = mapped_column(String, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    asr_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
