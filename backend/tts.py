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
DEFAULT_SENTENCE_PAUSE = 0.4   # seconds between sentences
DEFAULT_CLAUSE_PAUSE = 0.18    # seconds between clauses inside a long sentence
DEFAULT_LONG_SENTENCE_WORDS = 14  # threshold to trigger clause-level breaks
_MODELS_DIR = Path(__file__).resolve().parent.parent / "models" / "piper"

# Sentence splitter — see Fix 1 in catalog.py for the same regex shape.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[a-z]{2}[.!?])\s+(?=[A-Z])")
# Clause splitter — splits on comma or semicolon followed by whitespace.
# Won't split inside numbers like "200,000" because there's no whitespace.
_CLAUSE_SPLIT_RE = re.compile(r"(?<=[,;])\s+")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _segments_with_pauses(text: str) -> list[tuple[str, float]]:
    """Return [(spoken_segment, pause_seconds_after), ...] for the text.
    Long sentences (> threshold words) get split into clauses (on commas
    / semicolons) with a SHORTER pause between them, so a 30-word sentence
    sounds like a real person taking breaths instead of a non-stop wall."""
    sentence_pause = float(os.environ.get("TTS_SENTENCE_PAUSE", DEFAULT_SENTENCE_PAUSE))
    clause_pause = float(os.environ.get("TTS_CLAUSE_PAUSE", DEFAULT_CLAUSE_PAUSE))
    long_threshold = int(os.environ.get("TTS_LONG_SENTENCE_WORDS", DEFAULT_LONG_SENTENCE_WORDS))

    sentences = _split_sentences(text)
    segments: list[tuple[str, float]] = []
    for s_idx, sentence in enumerate(sentences):
        is_last_sentence = s_idx == len(sentences) - 1
        end_pause = 0.0 if is_last_sentence else sentence_pause

        if len(sentence.split()) > long_threshold and clause_pause > 0:
            clauses = [c.strip() for c in _CLAUSE_SPLIT_RE.split(sentence) if c.strip()]
            for c_idx, clause in enumerate(clauses):
                if c_idx < len(clauses) - 1:
                    segments.append((clause, clause_pause))
                else:
                    segments.append((clause, end_pause))
        else:
            segments.append((sentence, end_pause))
    return segments


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
    """Synthesize text to 16-bit PCM WAV bytes via Piper.

    Pauses inserted between segments for natural-sounding pacing:
    - Between sentences: TTS_SENTENCE_PAUSE seconds (default 0.4s)
    - Between clauses inside a long (>14 word) sentence: TTS_CLAUSE_PAUSE
      seconds (default 0.18s) — at commas / semicolons. Makes long
      sentences sound like a real person taking a breath, not a wall."""
    if not text:
        return b""
    try:
        v = _voice()
        segments = _segments_with_pauses(text)
        if not segments:
            return b""

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            # First segment: synthesize_wav sets WAV header + writes audio.
            first_text, _ = segments[0]
            v.synthesize_wav(first_text, wav)

            n_channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()

            for i in range(1, len(segments)):
                # Pause AFTER the previous segment, BEFORE this one.
                prev_pause = segments[i - 1][1]
                if prev_pause > 0:
                    n_silence = int(sample_rate * prev_pause)
                    wav.writeframes(bytes(n_silence * n_channels * sample_width))
                seg_text, _ = segments[i]
                v.synthesize_wav(seg_text, wav, set_wav_format=False)

        return buf.getvalue()
    except Exception as e:  # noqa: BLE001
        raise TTSFailure(
            f"piper-tts failed: {type(e).__name__}: {e}"
        ) from e
