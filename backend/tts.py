"""TTS wrapper around edge-tts. Step 1.8 - free cloud TTS for the May 30 demo.

Voice is configurable via env var TTS_VOICE. Defaults to a US male voice
(en-US-GuyNeural) for CJ Panganiban's persona. Other male English options:
  - en-US-AndrewNeural (friendlier, younger)
  - en-US-EricNeural (younger)
  - en-GB-RyanNeural (British)
  - en-AU-WilliamNeural (Australian)
Run `edge-tts --list-voices` for the full catalog.
"""

from __future__ import annotations

import asyncio
import os

from edge_tts import Communicate

DEFAULT_VOICE = "en-US-GuyNeural"


def synthesize(text: str, voice: str | None = None) -> bytes:
    voice = voice or os.environ.get("TTS_VOICE", DEFAULT_VOICE)
    return asyncio.run(_synthesize_async(text, voice))


async def _synthesize_async(text: str, voice: str) -> bytes:
    communicate = Communicate(text, voice)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)
