from abc import ABC, abstractmethod


class DiarizationProvider(ABC):
    @abstractmethod
    async def diarize(self, audio_path: str) -> list[dict]:
        raise NotImplementedError
