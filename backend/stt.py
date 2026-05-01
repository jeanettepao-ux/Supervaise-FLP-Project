"""STT wrapper around faster-whisper. Step 1.4 — local mic transcription."""

from __future__ import annotations

import io
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download

load_dotenv()

# Models cached project-local under ./models so we don't depend on the HF
# symlink-based cache (which needs Windows Developer Mode / admin).
_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


@lru_cache(maxsize=1)
def _model() -> WhisperModel:
    name = os.environ.get("WHISPER_MODEL", "base")
    local_dir = _MODELS_DIR / f"faster-whisper-{name}"
    if not local_dir.exists():
        local_dir.parent.mkdir(parents=True, exist_ok=True)
        snapshot_download(
            repo_id=f"Systran/faster-whisper-{name}",
            local_dir=str(local_dir),
        )
    return WhisperModel(str(local_dir), device="cpu", compute_type="int8")


def transcribe(audio) -> str:
    if isinstance(audio, (bytes, bytearray)):
        audio = io.BytesIO(audio)
    segments, _info = _model().transcribe(audio, beam_size=1)
    return " ".join(seg.text.strip() for seg in segments).strip()
