"""DNSMOS P.835: Microsoft's pretrained non-intrusive speech-quality model.

Gives three 1-5 mean-opinion scores for a recording WITHOUT a clean
reference: SIG (speech quality), BAK (background noise), OVRL (overall).
Used as the input features of gate comp1-C. Model file and licence
(CC BY 4.0): models/dnsmos/README.md.

Preprocessing follows Microsoft's reference script (DNSMOS/dnsmos_local.py):
resample to 16 kHz, repeat short clips up to 9.01 s, score every 9.01 s window
(1 s hop), map raw outputs through the published polynomials, average.

Optional: needs `onnxruntime`. is_available() lets callers skip cleanly.
"""

from pathlib import Path

import librosa
import numpy as np

DNSMOS_SR = 16000
INPUT_LENGTH_S = 9.01
HOP_S = 1.0
SCORE_KEYS = ("dnsmos_sig", "dnsmos_bak", "dnsmos_ovrl")

# Published calibration polynomials (non-personalised model), highest power first.
POLY_SIG = np.poly1d([-0.08397278, 1.22083953, 0.0052439])
POLY_BAK = np.poly1d([-0.13166888, 1.60915514, -0.39604546])
POLY_OVRL = np.poly1d([-0.06766283, 1.11546468, 0.04602535])


def is_available(model_path: str | Path) -> bool:
    """True if onnxruntime is installed and the model file exists."""
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return Path(model_path).is_file()


class DnsmosScorer:
    """Load the ONNX model once; call with (y, sr) to get the three scores."""

    def __init__(self, model_path: str | Path):
        import onnxruntime as ort  # optional dependency, imported only when used

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1   # single thread: identical results every run
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_path), sess_options=options,
                                            providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def _windows(self, y: np.ndarray) -> list[np.ndarray]:
        """9.01 s windows at a 1 s hop; short audio is repeated until it is long enough."""
        need = int(INPUT_LENGTH_S * DNSMOS_SR)
        if len(y) == 0:
            y = np.zeros(need)
        while len(y) < need:
            y = np.concatenate([y, y])
        n_windows = int(np.floor(len(y) / DNSMOS_SR) - INPUT_LENGTH_S) + 1
        hop = int(HOP_S * DNSMOS_SR)
        return [y[i * hop: i * hop + need] for i in range(n_windows) if len(y[i * hop: i * hop + need]) == need]

    def __call__(self, y: np.ndarray, sr: int) -> dict[str, float]:
        """Mean SIG, BAK and OVRL over all windows."""
        audio = np.asarray(y, dtype=np.float64)
        if sr != DNSMOS_SR:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=DNSMOS_SR)
        sig, bak, ovrl = [], [], []
        for window in self._windows(audio):
            raw = self.session.run(None, {self.input_name: window.astype(np.float32)[np.newaxis, :]})[0][0]
            sig.append(POLY_SIG(raw[0]))
            bak.append(POLY_BAK(raw[1]))
            ovrl.append(POLY_OVRL(raw[2]))
        return {"dnsmos_sig": float(np.mean(sig)), "dnsmos_bak": float(np.mean(bak)),
                "dnsmos_ovrl": float(np.mean(ovrl))}
