"""STT wrapper around faster-whisper. Step 1.4 - local mic transcription."""

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


# Domain prompt — primes Whisper to spell our key proper nouns and topics
# correctly instead of guessing phonetically. Big accuracy win for free.
# Kept short; Whisper truncates initial_prompt at ~224 tokens.
DOMAIN_PROMPT = (
    "Chief Justice Artemio V. Panganiban; "
    "Foundation for Liberty and Prosperity, FLP; "
    "A Centenary of Justice; Supreme Court of the Philippines; "
    "Inquirer column; West Philippine Sea, WPS; "
    "Estrada v. Desierto; Cruz v. Secretary of Environment; "
    "Bagong Bayani; Comelec; ICC; "
    "rule of law; jurisprudence; donor engagement."
)


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
    segments, _info = _model().transcribe(
        audio,
        language="en",                  # force English decoding (no auto-detect mistakes)
        beam_size=5,                    # better accuracy on ambiguous phonemes
        initial_prompt=DOMAIN_PROMPT,   # prime with domain terms
    )
    return " ".join(seg.text.strip() for seg in segments).strip()
