import asyncio
import inspect
import logging
import random
import time

from app.core.config import settings
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    async def generate(self, system_prompt: str, user_prompt: str, response_schema: dict) -> str:
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        def call_groq(output_mode: str = "object") -> str:
            from openai import APIStatusError, OpenAI, RateLimitError

            client = OpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
                max_retries=0,
            )
            max_attempts = max(1, settings.LLM_MAX_ATTEMPTS)
            for attempt in range(max_attempts):
                try:
                    response_format = {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "meeting_result",
                            "strict": True,
                            "schema": response_schema,
                        },
                    }
                    request_kwargs = {
                        "model": settings.LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.1,
                    }
                    if output_mode == "object":
                        response_format = {"type": "json_object"}
                    elif output_mode == "plain":
                        response_format = None
                    if response_format is not None:
                        request_kwargs["response_format"] = response_format
                    response = client.chat.completions.create(**request_kwargs)
                    content = response.choices[0].message.content
                    if not content:
                        raise RuntimeError("LLM returned an empty response.")
                    return content
                except RateLimitError as exc:
                    retry_after = None
                    response = getattr(exc, "response", None)
                    if response is not None:
                        retry_after_value = response.headers.get("retry-after")
                        if retry_after_value:
                            try:
                                retry_after = float(retry_after_value)
                            except (TypeError, ValueError):
                                pass

                    if retry_after is not None and retry_after > settings.LLM_MAX_RATE_LIMIT_WAIT_SECONDS:
                        minutes = retry_after / 60
                        raise RuntimeError(
                            "Groq rate limit is still active. "
                            f"The API reports a reset in about {minutes:.0f} minutes "
                            f"({retry_after:.0f} seconds). Wait and retry, or use another Groq key."
                        ) from None
                    if attempt == max_attempts - 1:
                        raise RuntimeError(
                            f"Groq rate limit exceeded after {max_attempts} attempts. "
                            "Wait briefly and retry the meeting."
                        ) from None
                    delay = retry_after if retry_after is not None else min(30, (2**attempt) + random.uniform(0, 1))
                    logger.warning("Groq rate limit hit; retrying in %.1f seconds", delay)
                    time.sleep(delay)
                except APIStatusError as exc:
                    detail = getattr(exc, "body", None) or str(exc)
                    is_json_validation_error = "json_validate_failed" in str(detail)
                    if is_json_validation_error and output_mode == "object":
                        logger.warning("Groq JSON object generation failed; retrying with prompt-only JSON mode.")
                        return call_groq(output_mode="plain")
                    if exc.status_code == 413 or "tokens per minute" in str(detail).casefold():
                        raise RuntimeError(
                            "Groq rejected the summary request because it is too large for the model's "
                            "token limit. Reduce TRANSCRIPT_CHUNK_CHARS and retry the meeting."
                        ) from exc
                    if exc.status_code is not None and exc.status_code >= 500 and attempt < 3:
                        delay = min(30, (2**attempt) + random.uniform(0, 1))
                        logger.warning("Groq server error %s; retrying in %.1f seconds", exc.status_code, delay)
                        time.sleep(delay)
                        continue
                    if exc.status_code == 400:
                        raise RuntimeError(f"Groq structured output was rejected: {detail}") from exc
                    raise
            raise RuntimeError("Groq request failed unexpectedly.")

        result = asyncio.to_thread(call_groq)
        return await result if inspect.isawaitable(result) else result


def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER.lower() == "groq":
        return GroqProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")
