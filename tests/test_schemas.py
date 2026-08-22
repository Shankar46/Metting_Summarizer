from pydantic import ValidationError
import pytest

from app.api.schemas import ActionItem, MeetingResult


def test_action_item_defaults():
    item = ActionItem(task="Send deployment notes")
    assert item.owner == "Unassigned"
    assert item.deadline == "Not specified"
    assert item.priority == "not_specified"


def test_action_item_rejects_empty_task():
    with pytest.raises(ValidationError):
        ActionItem(task="")


def test_meeting_result_validation():
    result = MeetingResult(
        summary="The team agreed on the launch plan.",
        key_decisions=[{"description": "Launch on Friday."}],
        action_items=[{"task": "Prepare deployment", "owner": "Asha", "priority": "high"}],
        open_questions=[{"question": "Who owns post-launch monitoring?"}],
    )
    assert result.action_items[0].priority == "high"


def test_invalid_priority_rejected():
    with pytest.raises(ValidationError):
        ActionItem(task="Prepare release", priority="urgent")
