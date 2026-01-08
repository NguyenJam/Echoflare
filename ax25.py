from __future__ import annotations

from dataclasses import dataclass


AX25_CONTROL_UI = 0x03
AX25_PID_NO_LAYER3 = 0xF0


@dataclass(frozen=True)
class AX25Address:
    callsign: str
    ssid: int = 0

    def encode(self, *, last: bool) -> bytes:
        callsign = self.callsign.upper()
        if len(callsign) > 6:
            raise ValueError(f"AX.25 callsign too long: {callsign!r}")
        if not (0 <= self.ssid <= 15):
            raise ValueError(f"AX.25 SSID must be 0..15, got {self.ssid}")

        call_bytes = callsign.ljust(6).encode("ascii")
        shifted = bytes(((b & 0x7F) << 1) for b in call_bytes)

        # SSID byte layout (AX.25):
        # bit 0: extension (1 = last address)
        # bits 1-4: SSID
        # bits 5-6: set to 1 (0x60) for AX.25 2.0+
        # bit 7: C bit / reserved (we leave 0)
        ssid_byte = 0x60 | ((self.ssid & 0x0F) << 1) | (0x01 if last else 0x00)
        return shifted + bytes([ssid_byte])

    @staticmethod
    def decode(addr7: bytes) -> "AX25Address":
        if len(addr7) != 7:
            raise ValueError("AX.25 address must be 7 bytes")

        call = bytes((b >> 1) & 0x7F for b in addr7[:6]).decode("ascii")
        callsign = call.rstrip(" ")
        ssid = (addr7[6] >> 1) & 0x0F
        return AX25Address(callsign=callsign, ssid=ssid)

    @staticmethod
    def is_last(addr7: bytes) -> bool:
        if len(addr7) != 7:
            raise ValueError("AX.25 address must be 7 bytes")
        return bool(addr7[6] & 0x01)


@dataclass(frozen=True)
class AX25Frame:
    destination: AX25Address
    source: AX25Address
    control: int
    pid: int
    payload: bytes

    def encode(self) -> bytes:
        header = (
            self.destination.encode(last=False)
            + self.source.encode(last=True)
            + bytes([self.control, self.pid])
        )
        return header + self.payload

    @staticmethod
    def decode(raw: bytes) -> "AX25Frame":
        if len(raw) < 7 + 7 + 2:
            raise ValueError("Frame too short to be AX.25")

        dst7 = raw[0:7]
        src7 = raw[7:14]
        if not AX25Address.is_last(src7):
            # This toolkit only supports the 2-address UI frame format.
            raise ValueError("Unsupported AX.25 frame: source address not marked last")

        control = raw[14]
        pid = raw[15]
        payload = raw[16:]

        return AX25Frame(
            destination=AX25Address.decode(dst7),
            source=AX25Address.decode(src7),
            control=control,
            pid=pid,
            payload=payload,
        )
