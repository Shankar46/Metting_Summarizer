from app.services.diarization.base import DiarizationProvider


class PyAnnoteDiarization(DiarizationProvider):
    """Extension point for future diarization; no fake speaker labels are generated."""

    async def diarize(self, audio_path: str) -> list[dict]:
        raise NotImplementedError("Speaker diarization is intentionally deferred for this assessment build.")
