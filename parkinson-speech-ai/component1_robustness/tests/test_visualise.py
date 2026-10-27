"""Tests for visualise.py: files exist, are valid, and are byte-for-byte reproducible."""

import matplotlib
import matplotlib.image as mpimg
import numpy as np
import pytest

from component1_robustness import visualise
from component1_robustness.config import load_config
from component1_robustness.enhancement import enhance
from component1_robustness.visualise import (
    DPI, FIGSIZE, plot_spectrograms, plot_waveforms, quality_titles, shared_db_range, shared_ylim,
)

SR = 16000
PLOTTERS = {"waveform": plot_waveforms, "spectrogram": plot_spectrograms}


@pytest.fixture(scope="module")
def pair():
    """A 5 dB noisy vowel and its Wiener-enhanced version."""
    from conftest import make_vowel
    clean = make_vowel()
    noise = np.random.default_rng(0).standard_normal(len(clean))
    raw = clean + noise * np.sqrt(np.mean(clean ** 2) / np.mean(noise ** 2)) / 10 ** (5 / 20)
    return raw, enhance(raw, SR, "wiener", load_config()["seed"])


def _png_chunk_types(data: bytes) -> list[bytes]:
    """Chunk type names of a PNG file (IHDR, IDAT, ...)."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    types, pos = [], 8
    while pos < len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        types.append(data[pos + 4:pos + 8])
        pos += 12 + length
    return types


def test_agg_backend():
    assert matplotlib.get_backend().lower() == "agg"


@pytest.mark.parametrize("kind", PLOTTERS)
def test_png_created_and_non_empty(kind, pair, tmp_path):
    raw, enhanced = pair
    out = PLOTTERS[kind](raw, enhanced, SR, tmp_path / "sub" / f"{kind}.png")
    assert out.is_file() and out.stat().st_size > 1000


@pytest.mark.parametrize("kind", PLOTTERS)
def test_fixed_pixel_size(kind, pair, tmp_path):
    raw, enhanced = pair
    image = mpimg.imread(PLOTTERS[kind](raw, enhanced, SR, tmp_path / f"{kind}.png"))
    assert image.shape[:2] == (FIGSIZE[1] * DPI, FIGSIZE[0] * DPI)


@pytest.mark.parametrize("kind", PLOTTERS)
def test_same_input_twice_identical_bytes(kind, pair, tmp_path):
    raw, enhanced = pair
    a = PLOTTERS[kind](raw, enhanced, SR, tmp_path / "a.png").read_bytes()
    b = PLOTTERS[kind](raw, enhanced, SR, tmp_path / "b.png").read_bytes()
    assert a == b


@pytest.mark.parametrize("kind", PLOTTERS)
def test_different_input_different_bytes(kind, pair, tmp_path):
    raw, enhanced = pair
    a = PLOTTERS[kind](raw, enhanced, SR, tmp_path / "a.png").read_bytes()
    b = PLOTTERS[kind](raw, raw, SR, tmp_path / "b.png").read_bytes()
    assert a != b


@pytest.mark.parametrize("kind", PLOTTERS)
def test_no_metadata_chunks(kind, pair, tmp_path):
    """No tIME (timestamp) and no text chunks (software version) in the PNG."""
    raw, enhanced = pair
    types = _png_chunk_types(PLOTTERS[kind](raw, enhanced, SR, tmp_path / "m.png").read_bytes())
    assert not {b"tIME", b"tEXt", b"iTXt", b"zTXt"} & set(types)


@pytest.mark.parametrize("kind", PLOTTERS)
def test_silence_does_not_crash(kind, tmp_path):
    out = PLOTTERS[kind](np.zeros(SR * 3), np.zeros(SR * 3), SR, tmp_path / "s.png")
    assert out.stat().st_size > 0


# --- Titles and shared scales --------------------------------------------------

def test_titles_show_before_and_after(pair):
    raw, enhanced = pair
    before, after = quality_titles(raw, enhanced, SR)
    assert before.startswith("Raw (") and after.startswith("Enhanced (")
    assert " dB)" in before and " dB)" in after
    assert ("SNR" in before or "HNR" in before) and ("SNR" in after or "HNR" in after)


def test_titles_use_given_estimates():
    titles = quality_titles(np.zeros(10), np.zeros(10), SR, before=(4.25, "hnr"), after=(12.0, "silence_snr"))
    assert titles == ("Raw (HNR 4.2 dB)", "Enhanced (SNR 12.0 dB)")


def test_titles_handle_minus_infinity():
    assert "-inf dB" in quality_titles(np.zeros(10), np.zeros(10), SR, (-np.inf, "hnr"), (0.0, "hnr"))[0]


def test_shared_ylim_fits_both():
    low, high = shared_ylim(np.array([0.2, -0.4]), np.array([0.9, -0.1]))
    assert low == -high and high == pytest.approx(0.9 * 1.05)


def test_shared_ylim_silence_not_zero_height():
    low, high = shared_ylim(np.zeros(5), np.zeros(5))
    assert high > low


def test_shared_db_range_spans_both():
    vmin, vmax = shared_db_range(np.array([[-50.0, -10.0]]), np.array([[-5.0, -70.0]]))
    assert vmax == -5.0 and vmin == -5.0 - visualise.SPEC_DYNAMIC_RANGE_DB
