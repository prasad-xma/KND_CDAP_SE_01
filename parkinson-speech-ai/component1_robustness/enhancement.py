"""Real audio enhancement/cleanup — the piece the proposal calls "Stage 4:
Enhancement / Cleanup Algorithms" (slide 17) that wasn't implemented yet.

Uses spectral-gating noise reduction (the `noisereduce` library): estimate a
noise profile from the recording itself and subtract it in the frequency
domain. This is a standard, well-established DSP technique (not a trained
model), so it needs no training data and works on any recording out of the
box — appropriate for a phase-1 quality-gate step.

This does NOT replace `degradation.py` (which synthetically damages clean
audio to study robustness) — this module does the opposite: it tries to
undo real-world damage on an incoming recording before Component 2/3 see it.
"""

import numpy as np
import noisereduce as nr
import soundfile as sf

from ..common.audio_io import ensure_wav


def enhance_audio(audio_path, output_path=None, stationary=False):
    """Denoise a recording via spectral gating.

    `stationary=False` (default) adapts to noise that changes over the
    recording — a reasonable default for phone recordings where background
    noise level isn't constant. Returns (denoised_signal, sample_rate), and
    also writes to `output_path` if given.
    """
    audio_path = ensure_wav(audio_path)
    y, sr = sf.read(audio_path, always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    y = y.astype(np.float32)

    denoised = nr.reduce_noise(y=y, sr=sr, stationary=stationary)

    if output_path:
        sf.write(output_path, denoised, sr)

    return denoised, sr
