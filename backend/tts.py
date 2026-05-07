"""TTS wrapper around edge-tts. Step 1.8 - free cloud TTS for the May 30 demo.

Voice is configurable via env var TTS_VOICE. Defaults to a US male voice
(en-US-GuyNeural). Other male English options:
  - en-US-AndrewNeural (friendlier, younger)
  - en-US-EricNeural (younger)
  - en-GB-RyanNeural (British)
  - en-AU-WilliamNeural (Australian)
Run `edge-tts --list-voices` for the full catalog.

Hardening (post-5a58664):
- Bounded per-attempt timeout so a hung Microsoft endpoint can't freeze a turn.
- Up to 2 retries with a small linear backoff for transient failures
  (rate-limit blips, transient network issues, dropped chunks).
- Raises TTSFailure on giving up. Callers should catch and fall back to
  text-only for that turn rather than letting the conversation break.
"""

from __future__ import annotations

import asyncio
import os
import time

from edge_tts import Communicate

DEFAULT_VOICE = "en-US-GuyNeural"
DEFAULT_RETRIES = 2
DEFAULT_TIMEOUT = 15.0  # seconds, per attempt


class TTSFailure(RuntimeError):
    """Raised when edge-tts fails after all retries."""


def synthesize(
    text: str,
    voice: str | None = None,
    *,
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
) -> bytes:
    voice = voice or os.environ.get("TTS_VOICE", DEFAULT_VOICE)
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return asyncio.run(_bounded_synthesize(text, voice, timeout))
        except Exception as e:  # noqa: BLE001 - intentional broad catch for retry
            last_exc = e
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))  # 0.5s, 1.0s
    raise TTSFailure(
        f"edge-tts failed after {retries + 1} attempts: "
        f"{type(last_exc).__name__}: {last_exc}"
    ) from last_exc


async def _bounded_synthesize(text: str, voice: str, timeout: float) -> bytes:
    return await asyncio.wait_for(_synthesize_async(text, voice), timeout=timeout)


async def _synthesize_async(text: str, voice: str) -> bytes:
    communicate = Communicate(text, voice)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)
