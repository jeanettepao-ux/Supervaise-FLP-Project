"""STT wrapper around faster-whisper. Step 1.4 - local mic transcription.

Two-layer accuracy strategy on the dev `small` model:
1. Expanded `initial_prompt` primes Whisper to spell our domain proper nouns
   correctly during decoding (chapter titles, case names, FLP, CJ, etc.).
2. Post-transcription `_domain_correct()` fixes whatever Whisper still
   mishears, via an explicit known-misheard dictionary plus a bounded
   fuzzy fallback against domain vocabulary.

Disable post-correction with STT_DOMAIN_CORRECT=false in env.
"""

from __future__ import annotations

import difflib
import io
import os
import re
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download

load_dotenv()

# Models cached project-local under ./models so we don't depend on the HF
# symlink-based cache (which needs Windows Developer Mode / admin).
_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


# =============================================================
# Layer (a) — primed initial_prompt
# =============================================================
# Whisper's initial_prompt window is ~224 tokens. We pack it with
# the key proper nouns, chapter titles, case names, and topic phrases
# the visitor is likely to say. Whisper biases its decoding toward
# producing these spellings rather than guessing phonetically.
DOMAIN_PROMPT = (
    "Chief Justice Artemio V. Panganiban, 21st Chief Justice of the "
    "Republic of the Philippines, founder of the Foundation for "
    "Liberty and Prosperity, also called FLP. He authored A Centenary "
    "of Justice and writes the Inquirer column With Due Respect. "
    "Topics: rule of law, jurisprudence, judicial reform, "
    "West Philippine Sea or WPS, International Criminal Court or ICC. "
    "Cases: Estrada v. Desierto, The Death Penalty, Cruz v. Secretary "
    "of Environment, Ang Bagong Bayani, Perez v. Estrada, Firestone "
    "Ceramics, Bengson v. House of Representatives, Social Weather "
    "Stations v. Comelec. Chapter titles: A Renaissance in the "
    "Judiciary, Old Doctrines and New Paradigms, Obra Maestra, "
    "Mediation, A Meaningful Centenary, E-Values for Lawyers."
)


# =============================================================
# Layer (b) — post-transcription correction
# =============================================================
# Layer (b1): explicit known mishearings. Case-insensitive regex with
# word boundaries. Add to this list as new mishearings are observed.
KNOWN_MISHEARDS: list[tuple[re.Pattern, str]] = [
    # Book title — the original "Ascentinary of Justice" failure
    (re.compile(r"\bAscentinary\s+of\s+Justice\b", re.IGNORECASE), "A Centenary of Justice"),
    (re.compile(r"\bAscentenary\s+of\s+Justice\b", re.IGNORECASE), "A Centenary of Justice"),
    (re.compile(r"\bAscentinary\b", re.IGNORECASE), "A Centenary"),
    (re.compile(r"\bAscentenary\b", re.IGNORECASE), "A Centenary"),

    # CJ's surname variants
    (re.compile(r"\bPanganibang\b", re.IGNORECASE), "Panganiban"),
    (re.compile(r"\bPanganivan\b", re.IGNORECASE), "Panganiban"),
    (re.compile(r"\bPanganibam\b", re.IGNORECASE), "Panganiban"),
    (re.compile(r"\bPonganiban\b", re.IGNORECASE), "Panganiban"),
    (re.compile(r"\bPangani\s+band\b", re.IGNORECASE), "Panganiban"),

    # "Centenary" mishearings
    (re.compile(r"\bCentinery\b", re.IGNORECASE), "Centenary"),
    (re.compile(r"\bCentenery\b", re.IGNORECASE), "Centenary"),
    (re.compile(r"\bSentenary\b", re.IGNORECASE), "Centenary"),
    (re.compile(r"\bSentinary\b", re.IGNORECASE), "Centenary"),

    # Case parties — names CJ uses in his writings. Whisper often phonetically
    # mangles Spanish-origin Filipino names. Add to this list as new
    # mishearings are observed during testing.
    (re.compile(r"\bEstraja\b", re.IGNORECASE), "Estrada"),
    (re.compile(r"\bEstrana\b", re.IGNORECASE), "Estrada"),
    (re.compile(r"\bComelek\b", re.IGNORECASE), "Comelec"),
    (re.compile(r"\bComeleck\b", re.IGNORECASE), "Comelec"),
    (re.compile(r"\bDesyerto\b", re.IGNORECASE), "Desierto"),
    (re.compile(r"\bCereto\b", re.IGNORECASE), "Desierto"),
    (re.compile(r"\bSerrato\b", re.IGNORECASE), "Desierto"),
    (re.compile(r"\bBengsen\b", re.IGNORECASE), "Bengson"),
    (re.compile(r"\bBensan\b", re.IGNORECASE), "Bengson"),
    (re.compile(r"\bSalonga\b", re.IGNORECASE), "Salonga"),  # canonical form (no-op)
    (re.compile(r"\bSolanga\b", re.IGNORECASE), "Salonga"),
    (re.compile(r"\bRobredo\b", re.IGNORECASE), "Robredo"),  # canonical
    (re.compile(r"\bRobreda\b", re.IGNORECASE), "Robredo"),

    # Foundation phrasing
    (re.compile(r"\bFoundation\s+for\s+Liberty\s+Prosperity\b", re.IGNORECASE),
     "Foundation for Liberty and Prosperity"),

    # Acronyms — ensure proper case
    (re.compile(r"\bflp\b"), "FLP"),
    (re.compile(r"\bwps\b"), "WPS"),
    (re.compile(r"\bicc\b"), "ICC"),
    (re.compile(r"\bcj\b"), "CJ"),
]


# Layer (b2): fuzzy fallback against domain vocabulary, applied only to
# capitalized non-trivial tokens. Tight cutoff (0.85) so common English
# words don't accidentally get rewritten as domain terms.
DOMAIN_TERMS: list[str] = [
    # People mentioned in CJ's corpus (helps Whisper bias toward correct
    # spellings when audio is acoustically ambiguous)
    "Panganiban", "Estrada", "Desierto", "Bengson", "Cruz", "Perez",
    "Salonga", "Robredo", "Marcos", "Duterte", "Aquino", "Arroyo",
    "Davide", "Trump", "Ressa", "Diokno", "Teehankee", "Carpio",
    "Kapunan", "Ynares", "Sandoval",
    # Organizations / acronyms
    "Foundation", "Inquirer", "Comelec", "Sandiganbayan", "Bayani",
    "Tan", "Yan", "Kee",  # Tan Yan Kee Foundation
    # Topics / book / cases
    "Centenary", "Renaissance", "Doctrines", "Paradigms", "Maestra",
    "Mediation", "Firestone", "Ceramics", "Liberty", "Prosperity",
    "Asean", "Inquirer", "Cathedral",
    # Court terms
    "Supreme", "Court", "Justice", "Judiciary", "Sandiganbayan",
]

_FUZZY_CUTOFF = 0.85
_FUZZY_MIN_LEN = 5  # don't fuzzy-match short tokens (too prone to false positives)


def _fuzzy_correct_token(match: "re.Match[str]") -> str:
    token = match.group(0)
    if len(token) < _FUZZY_MIN_LEN:
        return token
    best = difflib.get_close_matches(token, DOMAIN_TERMS, n=1, cutoff=_FUZZY_CUTOFF)
    return best[0] if best else token


def _domain_correct(text: str) -> str:
    """Two-stage post-transcription correction (Layer b1 + b2)."""
    out = text
    # Layer (b1): explicit known-misheard replacements
    for pattern, replacement in KNOWN_MISHEARDS:
        out = pattern.sub(replacement, out)
    # Layer (b2): fuzzy match capitalized tokens against domain vocab
    out = re.sub(r"\b[A-Z][a-zA-Z]+\b", _fuzzy_correct_token, out)
    return out


# Disable post-correction with STT_DOMAIN_CORRECT=false (e.g. for A/B testing)
DOMAIN_CORRECT_ENABLED = (
    os.environ.get("STT_DOMAIN_CORRECT", "true").lower() in ("true", "1", "yes")
)


# =============================================================
# Model + transcription entry point
# =============================================================
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
        language="en",
        beam_size=5,
        initial_prompt=DOMAIN_PROMPT,
    )
    raw = " ".join(seg.text.strip() for seg in segments).strip()
    return _domain_correct(raw) if DOMAIN_CORRECT_ENABLED else raw
