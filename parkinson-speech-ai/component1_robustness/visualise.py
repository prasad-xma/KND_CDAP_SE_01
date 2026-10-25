"""Before/after plots for the Component 1 report: waveform.png and spectrogram.png.

Reproducible by design: the same input always produces byte-identical PNGs.
    - Agg backend (no screen needed, no GUI state).
    - Fixed figure size and DPI.
    - No metadata in the PNG (no software version, no timestamp).
Raw and enhanced share one y scale (waveforms) and one colour scale
(spectrograms), so differences in the picture are differences in the audio.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # must be set before pyplot is imported

import librosa  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from component1_robustness.quality_metrics import estimate_quality_db  # noqa: E402

FIGSIZE = (10, 6)          # inches
DPI = 100                  # -> 1000 x 600 pixel PNG
N_FFT = 1024
HOP_LENGTH = 256
SPEC_DYNAMIC_RANGE_DB = 80.0
PNG_METADATA = {"Software": None}   # drop the default "Software: matplotlib x.y" text chunk
METHOD_LABELS = {"silence_snr": "SNR", "hnr": "HNR"}

Estimate = tuple[float, str]   # (dB, method) as returned by estimate_quality_db


def _label(estimate: Estimate) -> str:
    """'SNR 12.3 dB' or 'HNR 8.0 dB'."""
    db, method = estimate
    return f"{METHOD_LABELS.get(method, method)} {db:.1f} dB"


def quality_titles(raw: np.ndarray, enhanced: np.ndarray, sr: int,
                   before: Estimate | None = None, after: Estimate | None = None) -> tuple[str, str]:
    """Subplot titles with the SNR/HNR estimate before and after enhancement.

    Pass `before`/`after` if already computed; otherwise they are computed here.
    """
    before = before or estimate_quality_db(np.asarray(raw, dtype=np.float32), sr)
    after = after or estimate_quality_db(np.asarray(enhanced, dtype=np.float32), sr)
    return f"Raw ({_label(before)})", f"Enhanced ({_label(after)})"


def shared_ylim(raw: np.ndarray, enhanced: np.ndarray) -> tuple[float, float]:
    """Symmetric y-limits that fit both signals (never zero-height)."""
    peak = max(float(np.max(np.abs(raw), initial=0.0)), float(np.max(np.abs(enhanced), initial=0.0)))
    peak = max(peak, 1e-3) * 1.05
    return -peak, peak


def _power_db(y: np.ndarray) -> np.ndarray:
    """|STFT|^2 in dB, relative to 1.0 (absolute, so two signals are comparable)."""
    power = np.abs(librosa.stft(np.asarray(y, dtype=np.float32), n_fft=N_FFT, hop_length=HOP_LENGTH)) ** 2
    return librosa.power_to_db(power, ref=1.0, amin=1e-10, top_db=None)


def shared_db_range(raw_db: np.ndarray, enhanced_db: np.ndarray) -> tuple[float, float]:
    """One colour range for both spectrograms: loudest bin of either, down SPEC_DYNAMIC_RANGE_DB."""
    vmax = float(max(raw_db.max(), enhanced_db.max()))
    return vmax - SPEC_DYNAMIC_RANGE_DB, vmax


def _save(fig: plt.Figure, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, format="png", metadata=PNG_METADATA)
    plt.close(fig)
    return out_path


def plot_waveforms(raw: np.ndarray, enhanced: np.ndarray, sr: int, out_path: str | Path,
                   before: Estimate | None = None, after: Estimate | None = None) -> Path:
    """Raw above enhanced, same time axis and same y scale. Returns the PNG path."""
    titles = quality_titles(raw, enhanced, sr, before, after)
    ylim = shared_ylim(raw, enhanced)
    fig, axes = plt.subplots(2, 1, figsize=FIGSIZE, sharex=True)
    for ax, y, title in zip(axes, (raw, enhanced), titles):
        ax.plot(np.arange(len(y)) / sr, y, linewidth=0.5, color="tab:blue")
        ax.set_ylim(*ylim)
        ax.set_title(title)
        ax.set_ylabel("Amplitude")
    axes[-1].set_xlabel("Time (s)")
    fig.tight_layout()
    return _save(fig, out_path)


def plot_spectrograms(raw: np.ndarray, enhanced: np.ndarray, sr: int, out_path: str | Path,
                      before: Estimate | None = None, after: Estimate | None = None) -> Path:
    """Raw above enhanced log-power spectrograms on one shared colour scale. Returns the PNG path."""
    titles = quality_titles(raw, enhanced, sr, before, after)
    raw_db, enh_db = _power_db(raw), _power_db(enhanced)
    vmin, vmax = shared_db_range(raw_db, enh_db)
    fig, axes = plt.subplots(2, 1, figsize=FIGSIZE, sharex=True)
    for ax, spec, n, title in zip(axes, (raw_db, enh_db), (len(raw), len(enhanced)), titles):
        image = ax.imshow(spec, origin="lower", aspect="auto", cmap="magma", vmin=vmin, vmax=vmax,
                          extent=(0.0, n / sr, 0.0, sr / 2))
        ax.set_title(title)
        ax.set_ylabel("Frequency (Hz)")
    axes[-1].set_xlabel("Time (s)")
    fig.colorbar(image, ax=axes, label="Power (dB)")
    return _save(fig, out_path)
