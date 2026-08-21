import asyncio
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

        def call_groq() -> str:
            from openai import APIStatusError, OpenAI, RateLimitError

            client = OpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
                max_retries=0,
            )
            for attempt in range(4):
                try:
                    response = client.chat.completions.create(
                        model=settings.LLM_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": "meeting_result",
                                "strict": True,
                                "schema": response_schema,
                            },
                        },
                        temperature=0.1,
                    )
                    content = response.choices[0].message.content
                    if not content:
                        raise RuntimeError("LLM returned an empty response.")
                    return content
                except RateLimitError:
                    if attempt == 3:
                        raise RuntimeError("Groq rate limit exceeded after four attempts.") from None
                    delay = min(30, (2**attempt) + random.uniform(0, 1))
                    logger.warning("Groq rate limit hit; retrying in %.1f seconds", delay)
                    time.sleep(delay)
                except APIStatusError as exc:
                    if exc.status_code is not None and exc.status_code >= 500 and attempt < 3:
                        delay = min(30, (2**attempt) + random.uniform(0, 1))
                        logger.warning("Groq server error %s; retrying in %.1f seconds", exc.status_code, delay)
                        time.sleep(delay)
                        continue
                    if exc.status_code == 400:
                        detail = getattr(exc, "body", None) or str(exc)
                        raise RuntimeError(f"Groq structured output was rejected: {detail}") from exc
                    raise
            raise RuntimeError("Groq request failed unexpectedly.")

        return await asyncio.to_thread(call_groq)


def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER.lower() == "groq":
        return GroqProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")
