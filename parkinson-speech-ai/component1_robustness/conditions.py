"""Single source of truth for the degradation conditions used in Component 1.

experiment.py, evaluate_enhancement.py and validate_quality_gate.py all import
CONDITIONS, condition_rng() and degrade() from here, so every study uses
identical conditions AND identical random noise for the same clip.
"""

import zlib

import numpy as np

from component1_robustness.degradation import (
    add_synthetic_reverb,
    add_white_noise,
    apply_gain,
    simulate_compression,
)

# (name, spec) pairs. spec is None for the clean recording, otherwise (kind, parameter).
Spec = tuple[str, float | str] | None

CONDITIONS: list[tuple[str, Spec]] = [
    ("clean", None),
    ("noise_snr_10db", ("noise", 10)),
    ("noise_snr_5db", ("noise", 5)),
    ("noise_snr_0db", ("noise", 0)),
    ("noise_snr_-5db", ("noise", -5)),
    ("reverb_mild_rt0.3", ("reverb", 0.3)),
    ("reverb_heavy_rt0.6", ("reverb", 0.6)),
    ("compression_high", ("compression", "high")),
    ("compression_medium", ("compression", "medium")),
    ("compression_low", ("compression", "low")),
    ("distance_quiet_-6db", ("gain", -6)),
    ("distance_far_-12db", ("gain", -12)),
]


def condition_rng(seed: int, clip_id: str, condition_name: str) -> np.random.Generator:
    """Seeded rng for one (clip, condition) pair.

    Combines the config seed with stable hashes (CRC32) of the clip name and
    condition name, so a given clip under a given condition always gets the
    same noise — in every script, regardless of loop order.
    """
    keys = [seed, zlib.crc32(clip_id.encode("utf-8")), zlib.crc32(condition_name.encode("utf-8"))]
    return np.random.default_rng(np.random.SeedSequence(keys))


def degrade(y: np.ndarray, sr: int, spec: Spec, rng: np.random.Generator) -> np.ndarray:
    """Apply one degradation spec to signal y. spec=None returns y unchanged.

    rng (required) drives the random parts: noise and the reverb impulse response.
    """
    if spec is None:
        return y
    kind, param = spec
    if kind == "noise":
        return add_white_noise(y, snr_db=param, rng=rng)
    if kind == "reverb":
        return add_synthetic_reverb(y, sr, rt60_sec=param, rng=rng)
    if kind == "compression":
        return simulate_compression(y, sr, level=param)
    if kind == "gain":
        return apply_gain(y, gain_db=param)
    raise ValueError(f"Unknown degradation kind: {kind}")
