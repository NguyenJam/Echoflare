from __future__ import annotations

import hmac
import struct
from dataclasses import dataclass
from hashlib import sha256
from typing import Optional


HMAC_KEY_HEX = "13d942ddd4dd43ed5394039258c7b4c2a730b8ba1f4cc7b5dd24c3af623428e4"
HMAC_KEY = bytes.fromhex(HMAC_KEY_HEX)


class DecodeError(ValueError):
    pass


def _take(buf: memoryview, offset: int, n: int) -> tuple[memoryview, int]:
    end = offset + n
    if end > len(buf):
        raise DecodeError("Truncated payload")
    return buf[offset:end], end


def read_u8(buf: memoryview, offset: int) -> tuple[int, int]:
    chunk, offset = _take(buf, offset, 1)
    return int(chunk[0]), offset


def read_u16be(buf: memoryview, offset: int) -> tuple[int, int]:
    chunk, offset = _take(buf, offset, 2)
    return struct.unpack(">H", chunk)[0], offset


def read_u32be(buf: memoryview, offset: int) -> tuple[int, int]:
    chunk, offset = _take(buf, offset, 4)
    return struct.unpack(">I", chunk)[0], offset


def read_i16be(buf: memoryview, offset: int) -> tuple[int, int]:
    chunk, offset = _take(buf, offset, 2)
    return struct.unpack(">h", chunk)[0], offset


def read_i64be(buf: memoryview, offset: int) -> tuple[int, int]:
    chunk, offset = _take(buf, offset, 8)
    return struct.unpack(">q", chunk)[0], offset


def read_lp_string(buf: memoryview, offset: int) -> tuple[str, int]:
    n, offset = read_u8(buf, offset)
    chunk, offset = _take(buf, offset, n)
    try:
        return chunk.tobytes().decode("utf-8", errors="strict"), offset
    except UnicodeDecodeError:
        # Telemetry strings are expected to be simple ASCII/UTF-8.
        return chunk.tobytes().decode("latin1"), offset


def write_lp_string(s: str) -> bytes:
    data = s.encode("utf-8")
    if len(data) > 255:
        raise ValueError("String too long for length-prefixed encoding")
    return bytes([len(data)]) + data


@dataclass(frozen=True)
class TelemetryTL:
    sequence: int
    timestamp: int
    uptime: int
    boot_count: int
    restart_reason: int
    mode: int
    flags: int
    battery_voltages_mv: tuple[int, int, int]
    battery_currents_ma: tuple[int, int, int]
    temperature_c: float
    motd: str


def decode_telemetry(payload: bytes) -> TelemetryTL:
    buf = memoryview(payload)
    offset = 0

    packet_type, offset = read_u16be(buf, offset)
    if packet_type != 0x544C:
        raise DecodeError(f"Not a TL telemetry packet (type=0x{packet_type:04x})")

    sequence, offset = read_u32be(buf, offset)
    timestamp, offset = read_i64be(buf, offset)
    uptime, offset = read_u32be(buf, offset)
    boot_count, offset = read_u32be(buf, offset)

    restart_reason, offset = read_u8(buf, offset)
    mode, offset = read_u8(buf, offset)
    flags, offset = read_u8(buf, offset)

    bv = []
    bc = []
    for _ in range(3):
        v, offset = read_u16be(buf, offset)
        bv.append(v)
    for _ in range(3):
        c, offset = read_u16be(buf, offset)
        bc.append(c)

    temp_raw, offset = read_i16be(buf, offset)
    motd, offset = read_lp_string(buf, offset)

    return TelemetryTL(
        sequence=sequence,
        timestamp=timestamp,
        uptime=uptime,
        boot_count=boot_count,
        restart_reason=restart_reason,
        mode=mode,
        flags=flags,
        battery_voltages_mv=(bv[0], bv[1], bv[2]),
        battery_currents_ma=(bc[0], bc[1], bc[2]),
        temperature_c=temp_raw / 10.0,
        motd=motd,
    )


def build_telecommand(command_type: int, sequence: int, payload: bytes = b"") -> bytes:
    if not (0 <= command_type <= 0xFFFF):
        raise ValueError("command_type must fit uint16")
    if not (0 <= sequence <= 0xFFFFFFFF):
        raise ValueError("sequence must fit uint32")

    body = struct.pack(">HI", command_type, sequence) + payload
    mac = hmac.new(HMAC_KEY, body, sha256).digest()
    return body + mac


def build_set_motd(sequence: int, motd: str) -> bytes:
    return build_telecommand(0x5500, sequence, write_lp_string(motd))


def build_sstv(sequence: int) -> bytes:
    return build_telecommand(0x5533, sequence, b"")


def verify_telecommand(packet: bytes) -> Optional[str]:
    if len(packet) < 2 + 4 + 32:
        return "Telecommand too short"

    body = packet[:-32]
    sig = packet[-32:]
    expected = hmac.new(HMAC_KEY, body, sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return "Bad HMAC"
    return None
