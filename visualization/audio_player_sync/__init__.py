"""Custom Streamlit component: synchronized audio player.

Embeds an HTML5 audio player that reports its playback position back to
Python via the Streamlit component protocol. This lets the dashboard
update the Current Frame, Status, and Timeline cursor in real-time as
the audio plays, and freeze when the user pauses.
"""

from __future__ import annotations

import os
import streamlit.components.v1 as components

_COMPONENT_DIR = os.path.dirname(os.path.abspath(__file__))

_component_func = components.declare_component(
    "audio_player_sync",
    path=_COMPONENT_DIR,
)


def audio_player_sync(
    audio_url: str, seek_time: float = -1.0, key: str = "audio_sync"
) -> float:
    """Render an audio player and return the current playback time (seconds).

    Parameters
    ----------
    audio_url : str
        URL to the audio file, e.g. ``/app/static/current_audio.wav``.
    seek_time : float
        If >= 0, the player will instantly seek to this time and auto-play.
    key : str
        Unique Streamlit widget key to preserve iframe across reruns.

    Returns
    -------
    float
        The current playback position in seconds.
    """
    value = _component_func(
        audio_url=audio_url, seek_time=seek_time, key=key, default=0.0
    )
    return float(value) if value is not None else 0.0
