"""Tests for component2_phonation.vowel_segmentation."""

import numpy as np
import soundfile as sf

from component2_phonation.vowel_segmentation import (
    extract_longest_vowel_clip,
    extract_segment_to_wav,
    find_vowel_segments,
)

from conftest import TEST_DURATION_S, TEST_SR, make_silence, make_vowel


def _write_wav(tmp_path, y, name="clip.wav", sr=TEST_SR):
    path = tmp_path / name
    sf.write(path, y, sr)
    return str(path)


def test_silence_has_no_segments(tmp_path):
    path = _write_wav(tmp_path, make_silence())
    assert find_vowel_segments(path) == []


def test_continuous_vowel_is_one_segment_spanning_the_clip(tmp_path):
    path = _write_wav(tmp_path, make_vowel())
    segments = find_vowel_segments(path)
    assert len(segments) == 1
    start, end, duration = segments[0]
    assert duration > TEST_DURATION_S - 0.1


def test_two_vowel_bursts_are_two_segments_sorted_longest_first(tmp_path):
    long_burst = make_vowel(duration_s=1.5)
    short_burst = make_vowel(duration_s=0.5)
    gap = make_silence(duration_s=0.5)
    y = np.concatenate([long_burst, gap, short_burst])
    path = _write_wav(tmp_path, y)

    segments = find_vowel_segments(path)
    assert len(segments) == 2
    assert segments[0][2] > segments[1][2]


def test_extract_segment_to_wav_crops_the_requested_window(tmp_path):
    path = _write_wav(tmp_path, make_vowel(duration_s=3.0))
    out_path = extract_segment_to_wav(path, 1.0, 2.0, out_path=str(tmp_path / "crop.wav"))
    y, sr = sf.read(out_path)
    assert abs(len(y) / sr - 1.0) < 0.01


def test_extract_longest_vowel_clip_returns_none_for_silence(tmp_path):
    path = _write_wav(tmp_path, make_silence())
    assert extract_longest_vowel_clip(path) is None


def test_extract_longest_vowel_clip_returns_the_longer_burst(tmp_path):
    long_burst = make_vowel(duration_s=1.5)
    short_burst = make_vowel(duration_s=0.5)
    gap = make_silence(duration_s=0.5)
    y = np.concatenate([short_burst, gap, long_burst])
    path = _write_wav(tmp_path, y)

    result = extract_longest_vowel_clip(path, out_path=str(tmp_path / "longest.wav"))
    assert result is not None
    clip_path, start, end, duration = result
    assert duration > 1.0
