import json
import logging
from typing import Any

from app.api.schemas import MeetingResult
from app.core.config import settings
from app.prompts.meeting_prompt import (
    build_summarizer_prompt,
    get_summarizer_system_prompt,
)
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class MeetingSummarizer:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def summarize(self, transcript: list[dict[str, Any]]) -> MeetingResult:
        if not transcript:
            raise ValueError("Cannot summarize an empty transcript.")

        total_chars = sum(len(str(segment.get("text") or "")) for segment in transcript)
        if total_chars > settings.TRANSCRIPT_MAX_CHARS:
            raise ValueError(
                f"Transcript is too large to process safely ({total_chars:,} characters)."
            )

        chunks = self._chunk_transcript(transcript)
        results: list[MeetingResult] = []
        schema = self._strict_schema()

        for index, chunk in enumerate(chunks):
            logger.info("Summarizing transcript chunk %d/%d", index + 1, len(chunks))
            prompt = build_summarizer_prompt(self._format_transcript(chunk))
            raw = await self.llm.generate(get_summarizer_system_prompt(), prompt, schema)
            results.append(self._validate_response(raw))

        return self._merge_results(results)

    @staticmethod
    def _merge_results(results: list[MeetingResult]) -> MeetingResult:
        if not results:
            raise ValueError("No meeting analyses were produced.")
        if len(results) == 1:
            return results[0]

        decisions: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
        questions: list[dict[str, Any]] = []

        def append_unique(target: list[dict[str, Any]], item: dict[str, Any], key: str) -> None:
            value = str(item.get(key, "")).strip().casefold()
            if value and not any(str(existing.get(key, "")).strip().casefold() == value for existing in target):
                target.append(item)

        for result in results:
            for decision in result.key_decisions:
                append_unique(decisions, decision.model_dump(), "description")
            for action in result.action_items:
                append_unique(actions, action.model_dump(), "task")
            for question in result.open_questions:
                append_unique(questions, question.model_dump(), "question")

        summaries: list[str] = []
        for result in results:
            summary = result.summary.strip()
            if summary and summary.casefold() not in {item.casefold() for item in summaries}:
                summaries.append(summary)
        return MeetingResult(
            summary=" ".join(summaries) or "No summary was produced.",
            key_decisions=decisions,
            action_items=actions,
            open_questions=questions,
        )

    @staticmethod
    def _format_transcript(transcript: list[dict[str, Any]]) -> str:
        lines = []
        for segment in transcript:
            start = float(segment.get("start") or 0)
            text = str(segment.get("text") or "").strip()
            if text:
                lines.append(f"[{int(start // 60):02d}:{int(start % 60):02d}] {text}")
        return "\n".join(lines)

    @staticmethod
    def _validate_response(raw: str) -> MeetingResult:
        data = MeetingSummarizer._parse_json_response(raw)
        return MeetingResult.model_validate(data)

    @staticmethod
    def _parse_json_response(raw: str) -> dict[str, Any]:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        for index, character in enumerate(raw):
            if character != "{":
                continue
            try:
                data, _ = decoder.raw_decode(raw[index:])
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
        raise ValueError("Failed to parse LLM response as JSON.")

    @staticmethod
    def _strict_schema() -> dict:
        schema = MeetingResult.model_json_schema()

        def make_strict(node: dict) -> None:
            if node.get("type") == "object":
                node["additionalProperties"] = False
                properties = node.get("properties", {})
                node["required"] = list(properties)
                for property_schema in properties.values():
                    make_strict(property_schema)
            for nested in node.get("anyOf", []):
                if isinstance(nested, dict):
                    make_strict(nested)
            if isinstance(node.get("items"), dict):
                make_strict(node["items"])
            for definition in node.get("$defs", {}).values():
                make_strict(definition)

        make_strict(schema)
        return schema

    @staticmethod
    def _chunk_transcript(transcript: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        chunks: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_size = 0

        for segment in transcript:
            text = str(segment.get("text") or "")
            estimated_size = len(text) + 40
            if current and current_size + estimated_size > settings.TRANSCRIPT_CHUNK_CHARS:
                chunks.append(current)
                current = []
                current_size = 0
            current.append(segment)
            current_size += estimated_size

        if current:
            chunks.append(current)
        return chunks
