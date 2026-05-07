"""Robot adapter abstraction. WebAdapter for May 30; ReachyAdapter swaps in late July. Step 1.7."""

from __future__ import annotations

from typing import Any, Protocol

import streamlit as st

from backend.tts import synthesize


class RobotAdapter(Protocol):
    def speak(self, text: str, *, autoplay: bool = True) -> None: ...
    def head_move(self, pose: Any) -> None: ...
    def gaze_track(self, target: Any) -> None: ...
    def thinking_motion(self) -> None: ...
    def handle_interrupt(self, trigger: str) -> None: ...


class WebAdapter:
    """Streamlit web implementation. Voice out via local Piper TTS (WAV)."""

    def speak(self, text: str, *, autoplay: bool = True) -> None:
        st.write(text)
        try:
            audio = synthesize(text)
            if audio:
                st.audio(audio, format="audio/wav", autoplay=autoplay)
        except Exception as e:
            st.caption(f"(TTS unavailable: {e})")

    def head_move(self, pose: Any) -> None:
        pass

    def gaze_track(self, target: Any) -> None:
        pass

    def thinking_motion(self) -> None:
        pass

    def handle_interrupt(self, trigger: str) -> None:
        pass
