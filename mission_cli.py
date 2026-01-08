from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from echoflare.ax25 import AX25Address, AX25Frame, AX25_CONTROL_UI, AX25_PID_NO_LAYER3
from echoflare.groundtrack_api import GroundTrackClient, GroundTrackError, base_url_from_env
from echoflare.modem_g3ruh import demod_wav_to_ax25_frames, mod_ax25_frame_to_wav
from echoflare.proto import decode_telemetry, build_set_motd, build_sstv


def _find_latest_tl_sequence(ax25_frames: list[bytes]) -> tuple[int, dict] | None:
    best_seq = None
    best_tl = None
    for fr in ax25_frames:
        try:
            ax = AX25Frame.decode(fr)
            tl = decode_telemetry(ax.payload)
            if best_seq is None or tl.sequence > best_seq:
                best_seq = tl.sequence
                best_tl = asdict(tl)
        except Exception:
            continue
    if best_seq is None or best_tl is None:
        return None
    return int(best_seq), best_tl


def _find_latest_tl(ax25_frames: list[bytes]):
    best = None
    for fr in ax25_frames:
        try:
            ax = AX25Frame.decode(fr)
            tl = decode_telemetry(ax.payload)
            if best is None or tl.sequence > best.sequence:
                best = tl
        except Exception:
            continue
    return best


def _wrap_uplink_ax25(payload: bytes) -> bytes:
    frame = AX25Frame(
        destination=AX25Address("HA7FLR", ssid=0),
        source=AX25Address("GROUND", ssid=0),
        control=AX25_CONTROL_UI,
        pid=AX25_PID_NO_LAYER3,
        payload=payload,
    )
    return frame.encode()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="echoflare-mission",
        description="End-to-end helper: wait for pass, RX telemetry, TX MotD+SSTV",
    )
    p.add_argument(
        "--base-url",
        default=base_url_from_env(),
        help="Base URL of the GroundTrack site (or set ECHOFLARE_BASE_URL)",
    )
    p.add_argument("--satellite", default="Echoflare")
    p.add_argument("--min-elevation", type=float, default=10.0)
    p.add_argument("--motd", default="j_m0 was here")

    p.add_argument("--rx-telemetry-seconds", type=float, default=45.0)
    p.add_argument("--rx-sstv-seconds", type=float, default=75.0)

    p.add_argument(
        "--postcheck-seconds",
        type=float,
        default=45.0,
        help="Seconds of telemetry to capture after TX (for verifying sequence/MotD)",
    )
    p.add_argument(
        "--allow-sstv-without-motd",
        action="store_true",
        help="Proceed to SSTV even if MotD could not be verified as updated",
    )

    p.add_argument("--workdir", default="echoflare_runs", help="Directory for captured WAVs")

    return p


def main() -> int:
    args = build_parser().parse_args()
    if not args.base_url:
        raise SystemExit("Missing --base-url (or set ECHOFLARE_BASE_URL)")

    client = GroundTrackClient(args.base_url)

    print(f"Waiting for elevation >= {args.min_elevation} deg...")
    st = client.wait_for_elevation(args.satellite, min_elevation_deg=args.min_elevation, timeout_s=24 * 3600)
    print(json.dumps(st.raw, indent=2))

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time())
    rx_tlm = workdir / f"rx_telemetry_{ts}.wav"
    print(f"Capturing RX telemetry audio: {rx_tlm}")
    client.download_radio_wav(args.satellite, rx_tlm, seconds=args.rx_telemetry_seconds)

    print("Demodulating telemetry WAV...")
    demod = demod_wav_to_ax25_frames(rx_tlm)
    print(
        json.dumps(
            {
                "frames": len(demod.frames),
                "chosen_phase": demod.chosen_phase,
                "inverted": demod.inverted,
                "descramble_variant": demod.descramble_variant,
            },
            indent=2,
        )
    )

    tl0 = _find_latest_tl(demod.frames)
    if not tl0:
        raise SystemExit(
            "No decodable TL telemetry found in the capture. Try increasing --min-elevation or --rx-telemetry-seconds."
        )

    seq = int(tl0.sequence)
    tl_json = asdict(tl0)
    print("Latest decoded TL telemetry:")
    print(json.dumps(tl_json, indent=2))

    # 1) MotD telecommand at current sequence (single attempt + optional verify)
    print(f"Building MotD telecommand at sequence={seq}...")
    motd_tc = build_set_motd(seq, args.motd)
    motd_ax25 = _wrap_uplink_ax25(motd_tc)

    tx_motd_wav = workdir / f"tx_motd_{ts}.wav"
    mod_ax25_frame_to_wav(motd_ax25, tx_motd_wav)
    print(f"Uploading MotD TX WAV: {tx_motd_wav}")
    resp = client.upload_radio_wav(args.satellite, tx_motd_wav)
    print(resp)

    tl_after_motd = None
    rx_post = workdir / f"rx_post_motd_{ts}.wav"
    print(f"Capturing post-TX telemetry audio: {rx_post}")
    client.download_radio_wav(args.satellite, rx_post, seconds=args.postcheck_seconds)

    print("Demodulating post-TX telemetry WAV...")
    post_demod = demod_wav_to_ax25_frames(rx_post)
    print(
        json.dumps(
            {
                "frames": len(post_demod.frames),
                "chosen_phase": post_demod.chosen_phase,
                "inverted": post_demod.inverted,
                "descramble_variant": post_demod.descramble_variant,
            },
            indent=2,
        )
    )

    tl1 = _find_latest_tl(post_demod.frames)
    if tl1:
        print("Latest post-TX TL telemetry:")
        print(json.dumps(asdict(tl1), indent=2))
        seq = int(tl1.sequence)
        if tl1.motd == args.motd:
            tl_after_motd = tl1
            print("MotD verified updated.")
    else:
        print("No decodable TL telemetry in post-check capture.")

    if tl_after_motd is None and not args.allow_sstv_without_motd:
        raise SystemExit(
            "MotD could not be verified as updated. "
            "Re-run on a higher elevation pass, increase --postcheck-seconds, or pass --allow-sstv-without-motd."
        )

    # 2) SSTV telecommand
    # If we verified MotD, use the latest telemetry sequence as the next expected telecommand sequence.
    # Otherwise, fall back to seq+1 (best-effort).
    sstv_seq = int(tl_after_motd.sequence) if tl_after_motd is not None else ((seq + 1) & 0xFFFFFFFF)
    print(f"Building SSTV telecommand at sequence={sstv_seq}...")
    sstv_tc = build_sstv(sstv_seq)
    sstv_ax25 = _wrap_uplink_ax25(sstv_tc)

    tx_sstv_wav = workdir / f"tx_sstv_{ts}.wav"
    mod_ax25_frame_to_wav(sstv_ax25, tx_sstv_wav)
    print(f"Uploading SSTV TX WAV: {tx_sstv_wav}")
    resp = client.upload_radio_wav(args.satellite, tx_sstv_wav)
    print(resp)

    # 3) Capture SSTV downlink audio for later decoding
    rx_sstv = workdir / f"rx_sstv_{ts}.wav"
    print(f"Capturing RX SSTV audio: {rx_sstv}")
    client.download_radio_wav(args.satellite, rx_sstv, seconds=args.rx_sstv_seconds)

    print("Done. Next step: decode ROBOT36 from the saved rx_sstv_*.wav and read the signature.")
    print(str(rx_sstv))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
