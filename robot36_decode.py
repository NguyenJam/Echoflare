from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
from PIL import Image
from scipy import signal


@dataclass(frozen=True)
class Robot36Timings:
    sync_s: float = 0.009
    porch_s: float = 0.003
    y_s: float = 0.088
    sep_s: float = 0.0045
    c_s: float = 0.044

    @property
    def line_s(self) -> float:
        return self.sync_s + self.porch_s + self.y_s + self.sep_s + self.c_s


def _moving_average(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return x
    kernel = np.ones(n, dtype=np.float64) / float(n)
    return np.convolve(x, kernel, mode="same")


def _run_starts(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return list of (start,end) indices for True runs in mask."""
    if mask.size == 0:
        return []
    m = mask.astype(np.int8)
    dm = np.diff(m, prepend=m[0])
    starts = np.where(dm == 1)[0].tolist()
    ends = np.where(dm == -1)[0].tolist()
    if mask[0]:
        starts = [0] + starts
    if mask[-1]:
        ends = ends + [len(mask)]
    return list(zip(starts, ends))


def _pick_sync_chain(candidates: list[int], *, fs: int, line_s: float) -> list[int]:
    """Pick the longest chain of candidates spaced roughly one line apart."""
    if not candidates:
        return []

    target = int(round(line_s * fs))

    cand = np.array(sorted(set(int(x) for x in candidates)), dtype=np.int64)

    # Phase-cluster filter: true line syncs should occur at roughly a fixed offset modulo T.
    rem = (cand % target).astype(np.int64)
    bin_w = max(50, int(round(fs * 0.002)))  # ~2ms
    nb = max(1, target // bin_w)
    bins = np.minimum(rem // bin_w, nb - 1)
    counts = np.bincount(bins, minlength=nb)
    best_bin = int(np.argmax(counts))
    center = int(best_bin * bin_w + bin_w // 2)
    tol = max(200, int(round(fs * 0.004)))  # ~4ms

    phase_ok = np.abs(((rem - center + target // 2) % target) - target // 2) <= tol
    cand2 = cand[phase_ok]
    if cand2.size < 10:
        cand2 = cand

    # Track forward by expected times and accept nearest candidate within tolerance.
    step_tol = int(round(target * 0.25))  # ±25% of a line
    best: list[int] = []
    for start in range(min(50, len(cand2))):
        chain: list[int] = [int(cand2[start])]
        last = int(cand2[start])
        while True:
            want = last + target
            j = int(np.searchsorted(cand2, want))
            # choose the closest candidate to want
            nearest: Optional[int] = None
            best_err = None
            for k in (j - 2, j - 1, j, j + 1, j + 2):
                if 0 <= k < len(cand2):
                    v = int(cand2[k])
                    err = abs(v - want)
                    if best_err is None or err < best_err:
                        best_err = err
                        nearest = v
            if nearest is None or best_err is None or best_err > step_tol:
                break
            if nearest <= last:
                break
            chain.append(nearest)
            last = nearest
            if len(chain) >= 260:
                break
        if len(chain) > len(best):
            best = chain
        if len(best) >= 240:
            break

    return best


def _freq_to_byte(freq: np.ndarray) -> np.ndarray:
    # SSTV mapping: 1500 Hz -> 0, 2300 Hz -> 255
    v = (freq - 1500.0) * (255.0 / 800.0)
    return np.clip(v, 0.0, 255.0).astype(np.uint8)


def _ycbcr_to_rgb(y: np.ndarray, cb: np.ndarray, cr: np.ndarray) -> np.ndarray:
    # BT.601 full-range-ish conversion (good enough for decoding).
    y_f = y.astype(np.float32)
    cb_f = cb.astype(np.float32) - 128.0
    cr_f = cr.astype(np.float32) - 128.0

    r = y_f + 1.402 * cr_f
    g = y_f - 0.344136 * cb_f - 0.714136 * cr_f
    b = y_f + 1.772 * cb_f

    rgb = np.stack([r, g, b], axis=-1)
    return np.clip(rgb, 0.0, 255.0).astype(np.uint8)


def decode_robot36(
    wav_path: Path,
    *,
    out_path: Path,
    debug: bool = False,
    timings: Robot36Timings = Robot36Timings(),
) -> Path:
    import wave

    with wave.open(str(wav_path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("Expected 16-bit mono WAV")
        fs = int(w.getframerate())
        pcm = w.readframes(w.getnframes())

    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

    # Bandpass around SSTV tones.
    sos = signal.butter(6, [300, 4000], btype="bandpass", fs=fs, output="sos")
    xf = signal.sosfiltfilt(sos, x)

    # Instantaneous frequency via Hilbert transform.
    analytic = signal.hilbert(xf)
    phase = np.unwrap(np.angle(analytic))
    inst_freq = np.diff(phase) * (fs / (2.0 * math.pi))
    inst_freq = np.concatenate([inst_freq, inst_freq[-1:]])
    inst_freq = _moving_average(inst_freq, 5)

    # Find sync pulses (~1200 Hz for ~9ms). Instantaneous-frequency sample-by-sample
    # thresholds are fragile in noisy captures, so detect using STFT peak tracking.
    nperseg = 1024
    hop = 256
    noverlap = nperseg - hop
    f, t, Z = signal.stft(xf, fs=fs, nperseg=nperseg, noverlap=noverlap, boundary=None)
    mag = np.abs(Z)
    # Restrict to plausible SSTV tone band.
    band = (f >= 800) & (f <= 2600)
    f2 = f[band]
    mag2 = mag[band]
    peak_idx = np.argmax(mag2, axis=0)
    peak_f = f2[peak_idx]

    sync_frames = (peak_f >= 1080.0) & (peak_f <= 1320.0)
    frame_runs = _run_starts(sync_frames)
    # Need at least ~2 frames (~10ms) to qualify as a line sync.
    min_frames = max(2, int(round((timings.sync_s * 0.6) / (hop / fs))))

    candidates: list[int] = []
    for a, b in frame_runs:
        if b - a >= min_frames:
            # Convert frame index to sample index near the start of the run.
            candidates.append(int(round(t[a] * fs)))

    chain = _pick_sync_chain(candidates, fs=fs, line_s=timings.line_s)
    if debug:
        print(
            {
                "fs": fs,
                "samples": int(x.size),
                "duration_s": float(x.size) / float(fs),
                "sync_candidates": len(candidates),
                "picked_chain": len(chain),
                "line_s": timings.line_s,
            }
        )

    if len(chain) < 200:
        raise RuntimeError(
            f"Could not find a stable Robot36 line sync chain (found {len(chain)} lines). "
            "Try a different capture, or decode with RX-SSTV."
        )

    # Use the first 240 lines.
    chain = chain[:240]

    width = 320
    height = 240

    y_lines = np.zeros((height, width), dtype=np.uint8)
    cb_lines = np.zeros((height // 2, width), dtype=np.uint8)
    cr_lines = np.zeros((height // 2, width), dtype=np.uint8)

    y0 = timings.sync_s + timings.porch_s
    c0 = timings.sync_s + timings.porch_s + timings.y_s + timings.sep_s

    y_span = timings.y_s
    c_span = timings.c_s

    # Sample by indexing inst_freq at pixel centers.
    for i, sync_start in enumerate(chain):
        y_start = sync_start + int(round(y0 * fs))
        c_start = sync_start + int(round(c0 * fs))

        y_idx = y_start + (np.arange(width) + 0.5) * (y_span * fs / width)
        c_idx = c_start + (np.arange(width) + 0.5) * (c_span * fs / width)
        y_idx = np.clip(y_idx.astype(np.int64), 0, inst_freq.size - 1)
        c_idx = np.clip(c_idx.astype(np.int64), 0, inst_freq.size - 1)

        y_lines[i] = _freq_to_byte(inst_freq[y_idx])

        # Robot36 alternates chroma lines (Cb on even, Cr on odd) and applies them to pairs.
        pair = i // 2
        if i % 2 == 0:
            cb_lines[pair] = _freq_to_byte(inst_freq[c_idx])
        else:
            cr_lines[pair] = _freq_to_byte(inst_freq[c_idx])

    # Reconstruct RGB per 2-line block.
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    for pair in range(height // 2):
        cb = cb_lines[pair]
        cr = cr_lines[pair]
        for row in (2 * pair, 2 * pair + 1):
            rgb[row] = _ycbcr_to_rgb(y_lines[row], cb, cr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(out_path)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="robot36-decode", description="Decode Robot36 SSTV WAV into an image")
    p.add_argument("--wav", required=True, help="Input WAV (Robot36 SSTV audio)")
    p.add_argument("--out", required=True, help="Output image path (PNG recommended)")
    p.add_argument("--debug", action="store_true", help="Print decoding diagnostics")
    return p


def main() -> int:
    args = build_parser().parse_args()
    wav = Path(args.wav)
    out = Path(args.out)
    decode_robot36(wav, out_path=out, debug=bool(args.debug))
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
