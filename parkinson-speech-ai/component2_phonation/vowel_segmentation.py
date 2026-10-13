"""Extracts sustained-vowel segments from a continuous speech recording
(e.g. a Sinhala phrase), so Component 2's phonation features can be
computed on the vowel sounds embedded in natural speech rather than
requiring the user to say an isolated "aaaaaa".

Heuristic, not forced alignment: there's no Sinhala pronunciation
dictionary / acoustic model wired up here (Montreal Forced Aligner would be
the precise way to do this later - see the Dias/Wasala references from the
literature review). Instead this finds acoustically vowel-like stretches
directly: segments where Praat detects continuous voicing (an unbroken
pitch track) for at least MIN_SEGMENT_DURATION. Vowels are the longest
sustained-voicing stretches in normal speech - consonants (even voiced
ones like /m/, /n/, /l/) are comparatively brief, and unvoiced consonants
or pauses break the pitch track entirely - so ranking voiced runs by
duration and keeping the longest is a defensible phase-1 proxy for
"find the vowel sounds in this phrase" without a transcript or aligner.

This is a heuristic, not a validated phonetic segmenter - it will
sometimes catch a long voiced consonant or merge two short vowels
separated by a weak consonant. Treat the top segment as "probably the
held vowel," not a guaranteed-correct phonetic boundary.
"""

import os
import tempfile

import parselmouth
import soundfile as sf

from common.audio_io import ensure_wav

F0_MIN_HZ = 70
F0_MAX_HZ = 400
MIN_SEGMENT_DURATION = 0.15  # seconds - shorter than this is almost certainly a consonant, not a held vowel
PITCH_TIME_STEP = 0.01


def find_vowel_segments(audio_path, min_duration=MIN_SEGMENT_DURATION):
    """Returns a list of (start_seconds, end_seconds, duration_seconds) for
    each continuously-voiced stretch at least `min_duration` long, sorted by
    duration descending (longest / most vowel-like first).
    """
    audio_path = ensure_wav(audio_path)
    sound = parselmouth.Sound(audio_path)
    pitch = sound.to_pitch(time_step=PITCH_TIME_STEP, pitch_floor=F0_MIN_HZ, pitch_ceiling=F0_MAX_HZ)

    freqs = pitch.selected_array["frequency"]
    times = pitch.xs()
    voiced = freqs > 0

    segments = []
    seg_start = None
    for i, is_voiced in enumerate(voiced):
        if is_voiced and seg_start is None:
            seg_start = times[i]
        elif not is_voiced and seg_start is not None:
            segments.append((seg_start, times[i]))
            seg_start = None
    if seg_start is not None:
        segments.append((seg_start, times[-1]))

    segments = [(s, e, e - s) for s, e in segments if (e - s) >= min_duration]
    segments.sort(key=lambda seg: seg[2], reverse=True)
    return segments


def extract_segment_to_wav(audio_path, start_seconds, end_seconds, out_path=None):
    """Crops [start_seconds, end_seconds) out of audio_path and writes it as
    a new mono wav file, returning the output path.
    """
    audio_path = ensure_wav(audio_path)
    y, sr = sf.read(audio_path, always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)

    start_sample = int(start_seconds * sr)
    end_sample = int(end_seconds * sr)
    clip = y[start_sample:end_sample]

    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

    sf.write(out_path, clip, sr)
    return out_path


def extract_longest_vowel_clip(audio_path, out_path=None, min_duration=MIN_SEGMENT_DURATION):
    """Convenience wrapper: finds vowel segments and crops out the longest
    one. Returns (clip_path, start_seconds, end_seconds, duration_seconds),
    or None if no segment of at least `min_duration` was found.
    """
    segments = find_vowel_segments(audio_path, min_duration=min_duration)
    if not segments:
        return None
    start, end, duration = segments[0]
    clip_path = extract_segment_to_wav(audio_path, start, end, out_path=out_path)
    return clip_path, start, end, duration
