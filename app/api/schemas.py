from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ActionItem(BaseModel): 
    task: str = Field(min_length=1)
    owner: str | None = None
    deadline: str | None = None
    priority: Literal["high", "medium", "low", "not_specified"] = "not_specified"


class KeyDecision(BaseModel):
    description: str = Field(min_length=1)


class OpenQuestion(BaseModel):
    question: str = Field(min_length=1)


class MeetingResult(BaseModel):
    summary: str = Field(min_length=1)
    key_decisions: list[KeyDecision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)


class MeetingListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: str
    status: str
    duration: float | None = None
    summary_preview: str | None = None
    action_item_count: int = 0


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: str
    status: str
    duration: float | None = None
    audio_path: str | None = None
    transcript_json: list[dict[str, Any]] | None = None
    summary_markdown: str | None = None
    result: MeetingResult | None = None
    error_message: str | None = None
    asr_seconds: float | None = None
    summary_seconds: float | None = None
