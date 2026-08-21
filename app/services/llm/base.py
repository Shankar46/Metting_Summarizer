from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str, response_schema: dict) -> str:
        """Generate a schema-constrained JSON response."""
        raise NotImplementedError
