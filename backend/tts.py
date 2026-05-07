"""TTS wrapper around Piper (local neural TTS).

Replaces edge-tts. Piper:
- Runs entirely on local CPU. No internet round-trip at runtime.
- ~30-60 MB ONNX voice model, downloaded once into ./models/piper/.
- ~real-time speed on a typical laptop CPU.
- No rate limits, no API keys, no Microsoft endpoint flakiness.
- Multiple male English voices: ryan, joe, alan, bryce, etc.

Voice configurable via env:
  TTS_VOICE_PIPER=en_US-lessac-high   (default — engaging, expressive US male)
Other male options:
  en_GB-alan-medium     formal British, BBC-presenter feel
  en_US-bryce-medium    warm American male, conversational
  en_US-joe-medium      US male, mid-tone
  en_US-ryan-high       US male, deep but flat (less expressive)
  en_US-norman-medium   older US male, authoritative

Output format: 16-bit PCM WAV bytes (audio/wav). Streamlit's st.audio
plays them natively. The previous edge-tts wrapper returned MP3 bytes —
callers (WebAdapter, _synthesize_cached) now pass format="audio/wav".
"""

from __future__ import annotations

import io
import os
import wave
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
from piper import PiperVoice

load_dotenv()

DEFAULT_VOICE = "en_US-lessac-high"
_MODELS_DIR = Path(__file__).resolve().parent.parent / "models" / "piper"


class TTSFailure(RuntimeError):
    """Raised when Piper synthesis fails (e.g., model download failure)."""


def _voice_repo_path(voice_name: str) -> str:
    """Map a voice name like 'en_US-ryan-high' to its rhasspy/piper-voices
    repository path: 'en/en_US/ryan/high'."""
    parts = voice_name.split("-")
    if len(parts) < 3:
        raise ValueError(
            f"voice name {voice_name!r} should be like 'en_US-ryan-high' "
            "(language_country-speaker-quality)"
        )
    full_lang = parts[0]                 # "en_US"
    lang_short = full_lang.split("_")[0]  # "en"
    speaker = parts[1]                    # "ryan"
    quality = "-".join(parts[2:])         # "high" (or e.g. "medium")
    return f"{lang_short}/{full_lang}/{speaker}/{quality}"


@lru_cache(maxsize=1)
def _voice() -> PiperVoice:
    """Load the Piper voice model. First call downloads the .onnx + .json
    config from rhasspy/piper-voices into ./models/piper/. Subsequent calls
    use the lru_cache and the local files."""
    voice_name = os.environ.get("TTS_VOICE_PIPER", DEFAULT_VOICE)
    repo_path = _voice_repo_path(voice_name)
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    onnx_path = hf_hub_download(
        repo_id="rhasspy/piper-voices",
        filename=f"{repo_path}/{voice_name}.onnx",
        local_dir=str(_MODELS_DIR),
    )
    config_path = hf_hub_download(
        repo_id="rhasspy/piper-voices",
        filename=f"{repo_path}/{voice_name}.onnx.json",
        local_dir=str(_MODELS_DIR),
    )
    return PiperVoice.load(onnx_path, config_path=config_path)


def synthesize(text: str, voice: str | None = None) -> bytes:
    """Synthesize text to 16-bit PCM WAV bytes via Piper. Local, no network
    call at synthesis time, no retries needed (it doesn't fail on flaky
    cloud endpoints because there is no cloud endpoint)."""
    if not text:
        return b""
    try:
        v = _voice()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            # synthesize_wav sets channels/sample-rate/sample-width on the
            # wav file from the voice's config, then writes audio frames.
            v.synthesize_wav(text, wav)
        return buf.getvalue()
    except Exception as e:  # noqa: BLE001
        raise TTSFailure(
            f"piper-tts failed: {type(e).__name__}: {e}"
        ) from e
