"""TTS wrapper around gTTS. Step 1.8 - free cloud TTS for the May 30 demo."""

from __future__ import annotations

import io

from gtts import gTTS


def synthesize(text: str, lang: str = "en") -> bytes:
    tts = gTTS(text=text, lang=lang)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    return buf.getvalue()
