from __future__ import annotations

import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional


AX25_FLAG = 0x7E


def crc16_x25(data: bytes) -> int:
    """CRC-16/X-25 (AX.25 FCS) over bytes.

    - init: 0xFFFF
    - poly (reversed): 0x8408
    - xorout: 0xFFFF
    - transmitted little-endian
    """

    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return (~crc) & 0xFFFF


def bytes_to_bits_lsb_first(data: bytes) -> list[int]:
    bits: list[int] = []
    for b in data:
        for i in range(8):
            bits.append((b >> i) & 1)
    return bits


def bits_to_bytes_lsb_first(bits: Iterable[int]) -> bytes:
    out = bytearray()
    acc = 0
    n = 0
    for bit in bits:
        acc |= (int(bit) & 1) << n
        n += 1
        if n == 8:
            out.append(acc)
            acc = 0
            n = 0
    return bytes(out)


def bitstuff(bits: Iterable[int]) -> list[int]:
    out: list[int] = []
    ones = 0
    for bit in bits:
        bit = int(bit) & 1
        out.append(bit)
        if bit == 1:
            ones += 1
            if ones == 5:
                out.append(0)
                ones = 0
        else:
            ones = 0
    return out


def bitunstuff(bits: list[int]) -> list[int]:
    out: list[int] = []
    ones = 0
    i = 0
    while i < len(bits):
        bit = bits[i]
        out.append(bit)
        if bit == 1:
            ones += 1
            if ones == 5:
                # Next bit should be 0 and is stuffed
                if i + 1 < len(bits) and bits[i + 1] == 0:
                    i += 1
                ones = 0
        else:
            ones = 0
        i += 1
    return out


def nrzi_decode(levels: list[int]) -> list[int]:
    """NRZI: 0 = transition, 1 = no transition."""
    if not levels:
        return []
    bits: list[int] = []
    prev = levels[0]
    for lvl in levels[1:]:
        bits.append(1 if lvl == prev else 0)
        prev = lvl
    return bits


def nrzi_encode(bits: Iterable[int], *, initial_level: int = 1) -> list[int]:
    level = initial_level & 1
    out: list[int] = [level]
    for bit in bits:
        bit = int(bit) & 1
        if bit == 0:
            level ^= 1
        out.append(level)
    return out


def g3ruh_descramble(bits: list[int], *, variant: int) -> list[int]:
    """Self-synchronizing G3RUH descrambler.

    There are two common conventions in the wild for what is shifted into the LFSR.
    We try both to robustly recover HDLC flags.

    variant=0: out = in ^ tap11 ^ tap16; shift in *in*
    variant=1: out = in ^ tap11 ^ tap16; shift in *out*
    """

    lfsr = 0
    out_bits: list[int] = []
    for b in bits:
        b &= 1
        tap = ((lfsr >> 16) ^ (lfsr >> 11)) & 1
        out = b ^ tap
        out_bits.append(out)
        if variant == 0:
            lfsr = ((lfsr << 1) | b) & 0x1FFFF
        else:
            lfsr = ((lfsr << 1) | out) & 0x1FFFF
    return out_bits


def g3ruh_scramble(bits: list[int], *, variant: int) -> list[int]:
    # Same as descrambler for self-sync when using consistent shift convention.
    return g3ruh_descramble(bits, variant=variant)


@dataclass(frozen=True)
class DemodResult:
    frames: list[bytes]  # AX.25 frame bytes excluding flags and excluding FCS
    chosen_phase: int
    inverted: bool
    descramble_variant: int


def _extract_hdlc_frames(bits: list[int]) -> list[bytes]:
    """Extract AX.25 frames from a raw HDLC bitstream (already descrambled).

    Returns frames excluding flags and excluding the 2-byte FCS.
    """

    flag_bits = bytes_to_bits_lsb_first(bytes([AX25_FLAG]))

    # Find flag positions
    flags: list[int] = []
    for i in range(0, len(bits) - len(flag_bits) + 1):
        if bits[i : i + 8] == flag_bits:
            flags.append(i)

    frames: list[bytes] = []
    for a, b in zip(flags, flags[1:]):
        start = a + 8
        end = b
        if end <= start:
            continue

        payload_bits = bits[start:end]
        if len(payload_bits) < 8 * (7 + 7 + 2 + 2):
            continue

        unstuffed = bitunstuff(payload_bits)
        data = bits_to_bytes_lsb_first(unstuffed)
        if len(data) < 2:
            continue

        frame_wo_fcs = data[:-2]
        fcs_bytes = data[-2:]
        got_fcs = fcs_bytes[0] | (fcs_bytes[1] << 8)
        calc = crc16_x25(frame_wo_fcs)
        if got_fcs != calc:
            continue

        frames.append(frame_wo_fcs)

    return frames


def demod_wav_to_ax25_frames(path: Path, *, baud: int = 9600) -> DemodResult:
    """Best-effort demod for the GroundTrack /radio WAV stream.

    Assumptions (based on captured stream):
    - 48 kHz mono 16-bit PCM
    - 9600 bps NRZI + G3RUH scrambler + HDLC

    Returns decoded AX.25 frames (bytes excluding FCS).
    """

    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("Expected 16-bit PCM WAV")
        if w.getnchannels() != 1:
            raise ValueError("Expected mono WAV")
        fs = w.getframerate()
        pcm = w.readframes(w.getnframes())

    spb = fs / float(baud)
    if abs(spb - round(spb)) > 1e-6:
        raise ValueError(f"Sample rate {fs} not an integer multiple of baud {baud}")
    spb_i = int(round(spb))

    # Convert PCM to signed int16 list
    n = len(pcm) // 2
    samples = list(struct.unpack("<%dh" % n, pcm))

    best: Optional[DemodResult] = None

    for phase in range(spb_i):
        # Downsample by averaging each bit window
        levels: list[int] = []
        i = phase
        while i + spb_i <= len(samples):
            window = samples[i : i + spb_i]
            avg = sum(window) / spb_i
            levels.append(1 if avg >= 0 else 0)
            i += spb_i

        for inverted in (False, True):
            lev = [l ^ (1 if inverted else 0) for l in levels]
            bits_nrzi = nrzi_decode(lev)
            for variant in (0, 1):
                bits = g3ruh_descramble(bits_nrzi, variant=variant)
                frames = _extract_hdlc_frames(bits)
                if not frames:
                    continue

                cand = DemodResult(
                    frames=frames,
                    chosen_phase=phase,
                    inverted=inverted,
                    descramble_variant=variant,
                )
                if best is None or len(cand.frames) > len(best.frames):
                    best = cand

    return best or DemodResult(frames=[], chosen_phase=0, inverted=False, descramble_variant=0)


def mod_ax25_frame_to_wav(
    frame: bytes,
    out_path: Path,
    *,
    baud: int = 9600,
    fs: int = 48_000,
    amplitude: int = 20000,
    pre_flags: int = 32,
    post_flags: int = 8,
    scramble_variant: int = 0,
    initial_level: int = 1,
) -> Path:
    """Modulate an AX.25 frame (bytes excluding FCS) into a WAV suitable for /radio upload."""

    if fs % baud != 0:
        raise ValueError("fs must be an integer multiple of baud")
    spb = fs // baud

    fcs = crc16_x25(frame)
    frame_fcs = frame + struct.pack("<H", fcs)

    bits = bytes_to_bits_lsb_first(bytes([AX25_FLAG]) * pre_flags)
    bits += bitstuff(bytes_to_bits_lsb_first(frame_fcs))
    bits += bytes_to_bits_lsb_first(bytes([AX25_FLAG]) * post_flags)

    bits = g3ruh_scramble(bits, variant=scramble_variant)
    levels = nrzi_encode(bits, initial_level=initial_level)

    # levels -> PCM samples (rectangular pulses)
    pcm = bytearray()
    for lvl in levels:
        val = amplitude if lvl else -amplitude
        for _ in range(spb):
            pcm += struct.pack("<h", int(val))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(bytes(pcm))

    return out_path
