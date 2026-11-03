"""Create a deterministic one-second PCM WAV without overwriting a file."""
from __future__ import annotations

import math
from pathlib import Path
import struct
import wave


def make_sample(path: Path, seconds: int = 1) -> bytes:
    frames = b"".join(struct.pack("<h", round(8000 * math.sin(2 * math.pi * 440 * n / 16000)))
                      for n in range(16000 * seconds))
    with path.open("xb") as stream, wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(frames)
    return frames
