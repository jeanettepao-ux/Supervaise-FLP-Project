"""TTS wrapper around Piper (local neural TTS).

Replaces edge-tts. Piper:
- Runs entirely on local CPU. No internet round-trip at runtime.
- ~30-60 MB ONNX voice model, downloaded once into ./models/piper/.
- ~real-time speed on a typical laptop CPU.
- No rate limits, no API keys, no Microsoft endpoint flakiness.
- Multiple male English voices: ryan, joe, alan, bryce, etc.

Voice configurable via env:
  TTS_VOICE_PIPER=en_US-bryce-medium   (default — conversational US male)
Other verified MALE options:
  en_GB-alan-medium     formal British, BBC-presenter feel
  en_US-joe-medium      US male, mid-tone
  en_US-ryan-high       US male, deep but flat
  en_US-norman-medium   older US male, authoritative

NOTE: en_US-lessac-* and en_US-amy-* are FEMALE despite unisex-sounding
names — Arthur Lessac was a male voice coach, but the dataset was
recorded by a female reader.

Sentence pauses: piper-tts 1.4 dropped the SynthesisConfig.sentence_silence
field, so we add pauses ourselves by splitting on sentence boundaries,
synthesizing each piece, and writing silence frames between them.
Configurable via TTS_SENTENCE_PAUSE env (seconds, default 0.4).

Output format: 16-bit PCM WAV bytes (audio/wav). Streamlit's st.audio
plays them natively. The previous edge-tts wrapper returned MP3 bytes —
callers (WebAdapter, _synthesize_cached) now pass format="audio/wav".
"""

from __future__ import annotations

import io
import os
import re
import wave
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
from piper import PiperVoice

load_dotenv()

DEFAULT_VOICE = "en_US-bryce-medium"
DEFAULT_SENTENCE_PAUSE = 0.4  # seconds of silence between sentences
_MODELS_DIR = Path(__file__).resolve().parent.parent / "models" / "piper"

# Sentence splitter. Splits on . ! ? followed by whitespace + uppercase
# letter, BUT only when at least 2 LOWERCASE letters precede the period
# (avoids splitting on abbreviations like 'v.', 'Mr.', 'Dr.', 'Sr.' which
# only have 1 lowercase letter — the rest are uppercase).
#
# Examples:
#   "Estrada v. Desierto"       → 1 sentence (only 1 letter before "v.")
#   "Mr. Smith said hi."        → 1 sentence (only "r" lowercase before "Mr.")
#   "I wrote it. The case ruled" → 2 sentences ("it" = 2 lowercase)
#
# Known false-positive: "Plaintiff vs. Defendant" splits because "vs"
# is 2 lowercase letters. Rare in our corpus; CJ uses "v." not "vs.".
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[a-z]{2}[.!?])\s+(?=[A-Z])")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


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
    """Synthesize text to 16-bit PCM WAV bytes via Piper, with configurable
    silence inserted between sentences for natural-sounding pacing."""
    if not text:
        return b""
    pause_seconds = float(os.environ.get("TTS_SENTENCE_PAUSE", DEFAULT_SENTENCE_PAUSE))
    try:
        v = _voice()
        sentences = _split_sentences(text)
        if not sentences:
            return b""

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            # First sentence: synthesize_wav sets WAV header (channels,
            # sample rate, sample width) on the file AND writes audio.
            v.synthesize_wav(sentences[0], wav)

            if len(sentences) > 1 and pause_seconds > 0:
                # Build silence at the WAV's parameters (mono 16-bit @ rate).
                n_silence_frames = int(wav.getframerate() * pause_seconds)
                silence_bytes = bytes(
                    n_silence_frames * wav.getnchannels() * wav.getsampwidth()
                )
                for sentence in sentences[1:]:
                    wav.writeframes(silence_bytes)
                    # set_wav_format=False so it just appends frames without
                    # trying to re-write the header (which is already set).
                    v.synthesize_wav(sentence, wav, set_wav_format=False)
            elif len(sentences) > 1:
                # No pause requested — just stitch sentences end-to-end.
                for sentence in sentences[1:]:
                    v.synthesize_wav(sentence, wav, set_wav_format=False)

        return buf.getvalue()
    except Exception as e:  # noqa: BLE001
        raise TTSFailure(
            f"piper-tts failed: {type(e).__name__}: {e}"
        ) from e
