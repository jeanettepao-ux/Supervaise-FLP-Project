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


# =============================================================
# Pre-synthesis text normalization
# =============================================================
# Piper / eSpeak phonemizer makes some predictable mistakes on:
#  - Filipino names ("Duterte" pronounced "Dutert" — silent final 'e')
#  - Compact suffixes ("Jr." read as "J R" instead of "Junior")
#  - Currency notation ("P100,000" read as "P-100,000" not "100,000 pesos")
#  - 4-digit numbers in year contexts (1581 read as "one thousand five
#    hundred eighty-one" instead of "fifteen eighty-one")
#  - All-caps acronyms ("FLP" pronounced as one syllable, not letters)
#  - Compound proper nouns ("Mapa High" elided to "mapaha")
# We pre-process text before handing it to Piper to fix these.

# Phonetic respellings — for names Piper otherwise mispronounces.
# Use mixed case (no all-caps stretches) so the acronym-spacing rule
# doesn't shred them. Add new entries as we observe them; the UI shows
# the original spelling, only the synthesized audio uses these.
_PHONETIC_SPELLINGS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bDuterte\b"), "Doo terr teh"),    # silent-e fix
    (re.compile(r"\bMapa\s+High\b"), "Mah pah High"),
]

# Suffix expansions — full word instead of abbreviated letters.
_SUFFIX_EXPANSIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bMr\.(?=\s|$)"), "Mister"),
    (re.compile(r"\bMrs\.(?=\s|$)"), "Missus"),
    (re.compile(r"\bMs\.(?=\s|$)"), "Miss"),
    (re.compile(r"\bDr\.(?=\s|$)"), "Doctor"),
    (re.compile(r"\bJr\.(?=\s|$)"), "Junior"),
    (re.compile(r"\bSr\.(?=\s|$)"), "Senior"),
]

# Currency — Philippine peso notation. CJ writes 'P200,000' or 'P50 million'.
# Run BEFORE acronym spacing (the leading 'P' would otherwise be stripped).
_CURRENCY_EXPANSIONS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"\bP[-\s]*([\d,]+(?:\.\d+)?)\s+(million|billion|thousand)\b",
            re.IGNORECASE,
        ),
        r"\1 \2 pesos",
    ),
    (re.compile(r"\bP[-\s]*([\d,]+(?:\.\d+)?)\b"), r"\1 pesos"),
    (re.compile(r"\b₱[-\s]*([\d,]+(?:\.\d+)?)\b"), r"\1 pesos"),
]

# Year reading — speak 4-digit years naturally.
_YEAR_RE = re.compile(r"\b(1\d{3}|20\d{2})\b")

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]


def _num_to_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        if n % 10 == 0:
            return _TENS[n // 10]
        return _TENS[n // 10] + "-" + _ONES[n % 10]
    return str(n)  # fallback for >=100; not expected in our use


def _expand_year(match: "re.Match[str]") -> str:
    year = int(match.group(0))
    # 2000-2009: "two thousand", "two thousand five", etc.
    if 2000 <= year <= 2009:
        return "two thousand" if year == 2000 else f"two thousand {_num_to_words(year - 2000)}"
    # All other 4-digit years: split into two halves and read each.
    a, b = year // 100, year % 100
    if b == 0:
        return f"{_num_to_words(a)} hundred"
    if 0 < b < 10:
        # 1901 -> "nineteen oh one", 1808 -> "eighteen oh eight"
        return f"{_num_to_words(a)} oh {_num_to_words(b)}"
    return f"{_num_to_words(a)} {_num_to_words(b)}"


# Acronym spacing — pronounce 2-5 all-caps letter sequences as separate
# letters (FLP -> F L P, ICC -> I C C). Whitelist for acronyms commonly
# pronounced as one word (ASEAN, NATO).
_ACRONYM_RE = re.compile(r"\b([A-Z]{2,5})\b")
_ACRONYM_WORDS_SAY_AS_WORD = {"ASEAN", "NATO", "AIDS", "OPEC"}


def _space_acronym(match: "re.Match[str]") -> str:
    word = match.group(0)
    if word in _ACRONYM_WORDS_SAY_AS_WORD:
        return word
    return " ".join(word)


def _normalize_for_speech(text: str) -> str:
    """Pre-synthesis text transforms for natural Piper pronunciation.
    Applied to the text BEFORE sentence splitting and audio synthesis.
    Does not affect what visitors see in the chat UI — only what they hear."""
    out = text
    # Phonetic respellings first (before acronym spacing might break them)
    for pattern, repl in _PHONETIC_SPELLINGS:
        out = pattern.sub(repl, out)
    # Suffix expansions (Mr. -> Mister, etc.)
    for pattern, repl in _SUFFIX_EXPANSIONS:
        out = pattern.sub(repl, out)
    # Currency (P100,000 -> 100,000 pesos) — BEFORE acronyms strip leading 'P'
    for pattern, repl in _CURRENCY_EXPANSIONS:
        out = pattern.sub(repl, out)
    # Year reading (1581 -> fifteen eighty-one)
    out = _YEAR_RE.sub(_expand_year, out)
    # Acronym spacing (FLP -> F L P) — last, so prior rules already ran
    out = _ACRONYM_RE.sub(_space_acronym, out)
    return out

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
        # Apply pre-synthesis normalization (phonetic spellings, currency,
        # years, suffixes, acronym spacing) BEFORE sentence splitting.
        normalized = _normalize_for_speech(text)
        segments = _segments_with_pauses(normalized)
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
