"""Shared audio-loading helper: transparently handle non-WAV input.

soundfile/parselmouth only read WAV/FLAC/OGG-family files directly — phone
recordings are commonly .m4a/.mp3, which they reject outright. This converts
anything else to a temp mono WAV via a bundled ffmpeg binary (imageio-ffmpeg,
installed via pip — no system-wide ffmpeg install needed) so every
`extract_*_features` function can accept whatever format a real recording
shows up in.
"""

import os
import subprocess
import tempfile

import imageio_ffmpeg

_FFMPEG_EXE = None


def _ffmpeg():
    global _FFMPEG_EXE
    if _FFMPEG_EXE is None:
        _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
    return _FFMPEG_EXE


def ensure_wav(audio_path):
    """Return a path to a WAV version of audio_path, converting if needed."""
    if audio_path.lower().endswith(".wav"):
        return audio_path

    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    result = subprocess.run(
        [_ffmpeg(), "-y", "-i", audio_path, "-ar", "44100", "-ac", "1", tmp_path],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to convert {audio_path!r} to wav: {result.stderr.decode(errors='ignore')}"
        )

    return tmp_path
