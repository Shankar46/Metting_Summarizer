from abc import ABC, abstractmethod
from typing import Any


class ASRProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str) -> list[dict[str, Any]]:
        raise NotImplementedError
