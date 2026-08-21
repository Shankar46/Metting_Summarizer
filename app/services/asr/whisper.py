import asyncio
import logging
import os
import tempfile
from typing import Any

from app.core.config import settings
from app.services.asr.base import ASRProvider

logger = logging.getLogger(__name__)


class WhisperASR(ASRProvider):
    """Groq Whisper adapter with large-file chunking and normalized segments."""

    CHUNK_SIZE_BYTES = 24 * 1024 * 1024
    CHUNK_DURATION_MS = 10 * 60 * 1000

    @staticmethod
    def _value(obj: Any, field: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(field, default)
        return getattr(obj, field, default)

    async def transcribe(self, audio_path: str) -> list[dict[str, Any]]:
        provider = settings.ASR_PROVIDER.lower()
        if provider == "mock":
            return [
                {"start": 0.0, "end": 2.0, "text": "This is a mock transcript for local testing.", "speaker": None}
            ]
        if provider != "groq_whisper":
            raise ValueError(f"Unsupported ASR_PROVIDER: {settings.ASR_PROVIDER}")
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        if os.path.getsize(audio_path) > self.CHUNK_SIZE_BYTES:
            return await self._transcribe_large_file(audio_path)
        return await self._api_transcribe(audio_path)

    async def _transcribe_large_file(self, audio_path: str) -> list[dict[str, Any]]:
        try:
            from pydub import AudioSegment
        except ImportError as exc:
            raise RuntimeError("pydub is required for large-file chunking.") from exc

        audio = await asyncio.to_thread(AudioSegment.from_file, audio_path)
        temp_dir = tempfile.mkdtemp(prefix="meeting_chunks_")
        chunk_paths: list[str] = []
        try:
            for index, start_ms in enumerate(range(0, len(audio), self.CHUNK_DURATION_MS)):
                chunk = audio[start_ms : start_ms + self.CHUNK_DURATION_MS]
                chunk_path = os.path.join(temp_dir, f"chunk_{index}.mp3")
                await asyncio.to_thread(chunk.export, chunk_path, format="mp3", bitrate="128k")
                chunk_paths.append(chunk_path)

            segments: list[dict[str, Any]] = []
            offset_seconds = 0.0
            for chunk_path in chunk_paths:
                chunk_segments = await self._api_transcribe(chunk_path)
                for segment in chunk_segments:
                    segment["start"] += offset_seconds
                    segment["end"] += offset_seconds
                    segments.append(segment)
                offset_seconds += self.CHUNK_DURATION_MS / 1000.0
            return segments
        finally:
            for path in chunk_paths:
                try:
                    os.remove(path)
                except OSError:
                    logger.warning("Could not remove temporary chunk: %s", path)
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass

    async def _api_transcribe(self, audio_path: str) -> list[dict[str, Any]]:
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        def call_api():
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url=settings.GROQ_BASE_URL,
                max_retries=2,
            )
            kwargs = {
                "file": open(audio_path, "rb"),
                "model": settings.ASR_MODEL,
                "response_format": "verbose_json",
                "timestamp_granularities": ["segment"],
                "temperature": 0,
            }
            if settings.ASR_LANGUAGE:
                kwargs["language"] = settings.ASR_LANGUAGE
            try:
                return client.audio.transcriptions.create(**kwargs)
            finally:
                kwargs["file"].close()

        response = await asyncio.to_thread(call_api)
        raw_segments = self._value(response, "segments") or []

        if not raw_segments:
            text = str(self._value(response, "text", "") or "").strip()
            return [{"start": 0.0, "end": 0.0, "text": text, "speaker": None}] if text else []

        normalized = []
        for segment in raw_segments:
            text = str(self._value(segment, "text", "") or "").strip()
            if not text:
                continue
            normalized.append(
                {
                    "start": round(float(self._value(segment, "start", 0.0) or 0.0), 3),
                    "end": round(float(self._value(segment, "end", 0.0) or 0.0), 3),
                    "text": text,
                    # Do not fabricate speaker identities.
                    "speaker": self._value(segment, "speaker", None),
                }
            )
        return normalized
