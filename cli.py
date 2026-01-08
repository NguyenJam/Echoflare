from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from echoflare.ax25 import AX25Frame, AX25Address, AX25_CONTROL_UI, AX25_PID_NO_LAYER3
from echoflare.proto import decode_telemetry, build_set_motd, build_sstv, verify_telecommand
from echoflare.modem_g3ruh import demod_wav_to_ax25_frames, mod_ax25_frame_to_wav


def _parse_hex(s: str) -> bytes:
    s = s.strip().replace(" ", "").replace("\n", "").replace("\t", "")
    if s.startswith("0x"):
        s = s[2:]
    return bytes.fromhex(s)


def cmd_decode_ax25(args: argparse.Namespace) -> int:
    raw = _parse_hex(args.hex) if args.hex else Path(args.file).read_bytes()
    frame = AX25Frame.decode(raw)
    result = {
        "destination": {"callsign": frame.destination.callsign, "ssid": frame.destination.ssid},
        "source": {"callsign": frame.source.callsign, "ssid": frame.source.ssid},
        "control": frame.control,
        "pid": frame.pid,
        "payload_hex": frame.payload.hex(),
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_decode_telemetry(args: argparse.Namespace) -> int:
    raw = _parse_hex(args.hex) if args.hex else Path(args.file).read_bytes()

    if args.ax25:
        frame = AX25Frame.decode(raw)
        payload = frame.payload
    else:
        payload = raw

    tl = decode_telemetry(payload)
    print(json.dumps(asdict(tl), indent=2))
    return 0


def _wrap_ax25(payload: bytes, *, src: str, dst: str) -> bytes:
    frame = AX25Frame(
        destination=AX25Address(dst, ssid=0),
        source=AX25Address(src, ssid=0),
        control=AX25_CONTROL_UI,
        pid=AX25_PID_NO_LAYER3,
        payload=payload,
    )
    return frame.encode()


def cmd_build_motd(args: argparse.Namespace) -> int:
    tc = build_set_motd(sequence=args.sequence, motd=args.motd)
    err = verify_telecommand(tc)
    if err:
        raise SystemExit(f"internal error: produced invalid telecommand: {err}")

    out = _wrap_ax25(tc, src=args.src, dst=args.dst) if args.ax25 else tc

    if args.out:
        Path(args.out).write_bytes(out)
    if args.print_hex:
        print(out.hex())
    return 0


def cmd_build_sstv(args: argparse.Namespace) -> int:
    tc = build_sstv(sequence=args.sequence)
    err = verify_telecommand(tc)
    if err:
        raise SystemExit(f"internal error: produced invalid telecommand: {err}")

    out = _wrap_ax25(tc, src=args.src, dst=args.dst) if args.ax25 else tc

    if args.out:
        Path(args.out).write_bytes(out)
    if args.print_hex:
        print(out.hex())
    return 0


def cmd_demod_wav(args: argparse.Namespace) -> int:
    res = demod_wav_to_ax25_frames(Path(args.wav))
    print(
        json.dumps(
            {
                "frames": len(res.frames),
                "chosen_phase": res.chosen_phase,
                "inverted": res.inverted,
                "descramble_variant": res.descramble_variant,
            },
            indent=2,
        )
    )

    if not res.frames:
        return 0

    if args.print_hex:
        for fr in res.frames:
            print(fr.hex())

    if args.decode_tl:
        decoded = 0
        for fr in res.frames:
            try:
                ax = AX25Frame.decode(fr)
                tl = decode_telemetry(ax.payload)
                print(json.dumps(asdict(tl), indent=2))
                decoded += 1
            except Exception:
                continue

        if decoded == 0:
            print("No decodable TL telemetry found in these frames.")

    return 0


def cmd_mod_wav(args: argparse.Namespace) -> int:
    frame = _parse_hex(args.hex)
    mod_ax25_frame_to_wav(frame, Path(args.out))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="echoflare", description="Echoflare AX.25 + protocol helpers")
    sub = p.add_subparsers(required=True)

    p_ax = sub.add_parser("decode-ax25", help="Decode a raw 2-address AX.25 UI frame")
    g = p_ax.add_mutually_exclusive_group(required=True)
    g.add_argument("--hex", help="Frame as hex")
    g.add_argument("--file", help="Binary frame file")
    p_ax.set_defaults(func=cmd_decode_ax25)

    p_tl = sub.add_parser("decode-telemetry", help="Decode a TL telemetry payload (optionally wrapped in AX.25)")
    g = p_tl.add_mutually_exclusive_group(required=True)
    g.add_argument("--hex", help="Payload/frame as hex")
    g.add_argument("--file", help="Binary payload/frame file")
    p_tl.add_argument("--ax25", action="store_true", help="Input is a raw AX.25 UI frame")
    p_tl.set_defaults(func=cmd_decode_telemetry)

    p_m = sub.add_parser("build-motd", help="Build a signed Set-MotD telecommand")
    p_m.add_argument("--sequence", type=int, required=True, help="Sequence number from latest telemetry")
    p_m.add_argument("--motd", required=True, help="Message of the day")
    p_m.add_argument("--ax25", action="store_true", help="Wrap in AX.25 UI frame")
    p_m.add_argument("--src", default="GROUND", help="AX.25 source callsign (max 6 chars)")
    p_m.add_argument("--dst", default="HA7FLR", help="AX.25 destination callsign (max 6 chars)")
    p_m.add_argument("--out", help="Write binary output")
    p_m.add_argument("--print-hex", action="store_true", help="Print output as hex")
    p_m.set_defaults(func=cmd_build_motd)

    p_s = sub.add_parser("build-sstv", help="Build a signed SSTV telecommand")
    p_s.add_argument("--sequence", type=int, required=True, help="Sequence number from latest telemetry")
    p_s.add_argument("--ax25", action="store_true", help="Wrap in AX.25 UI frame")
    p_s.add_argument("--src", default="GROUND", help="AX.25 source callsign (max 6 chars)")
    p_s.add_argument("--dst", default="HA7FLR", help="AX.25 destination callsign (max 6 chars)")
    p_s.add_argument("--out", help="Write binary output")
    p_s.add_argument("--print-hex", action="store_true", help="Print output as hex")
    p_s.set_defaults(func=cmd_build_sstv)

    p_demod = sub.add_parser("demod-wav", help="Demod a GroundTrack /radio WAV into AX.25 frames")
    p_demod.add_argument("--wav", required=True, help="Path to WAV captured from /radio/<sat>")
    p_demod.add_argument("--print-hex", action="store_true", help="Print decoded AX.25 frames as hex")
    p_demod.add_argument("--decode-tl", action="store_true", help="Try decoding TL telemetry from frames")
    p_demod.set_defaults(func=cmd_demod_wav)

    p_mod = sub.add_parser("mod-wav", help="Modulate an AX.25 frame (hex) into a TX WAV")
    p_mod.add_argument("--hex", required=True, help="AX.25 frame bytes as hex (no flags, no FCS)")
    p_mod.add_argument("--out", required=True, help="Output WAV path")
    p_mod.set_defaults(func=cmd_mod_wav)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
