from __future__ import annotations

import argparse
import json
from pathlib import Path

from echoflare.groundtrack_api import GroundTrackClient, GroundTrackError, base_url_from_env


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="groundtrack", description="GroundTrack API helper (satellite status + radio audio)")
    p.add_argument(
        "--base-url",
        default=base_url_from_env(),
        help="Base URL of the GroundTrack site (or set ECHOFLARE_BASE_URL)",
    )

    sub = p.add_subparsers(required=True)

    s_list = sub.add_parser("list", help="List available satellites")
    s_list.set_defaults(cmd="list")

    s_status = sub.add_parser("status", help="Fetch current status for a satellite")
    s_status.add_argument("--satellite", required=True, help="Satellite id/name")
    s_status.set_defaults(cmd="status")

    s_wait = sub.add_parser("wait", help="Wait until elevation reaches a threshold")
    s_wait.add_argument("--satellite", required=True)
    s_wait.add_argument("--min-elevation", type=float, default=10.0)
    s_wait.add_argument("--timeout", type=float, default=15 * 60.0)
    s_wait.set_defaults(cmd="wait")

    s_rx = sub.add_parser("rx", help="Capture the /radio stream into a WAV file")
    s_rx.add_argument("--satellite", required=True)
    s_rx.add_argument("--out", required=True, help="Output WAV path")
    s_rx.add_argument("--seconds", type=float, default=30.0)
    s_rx.set_defaults(cmd="rx")

    s_tx = sub.add_parser("tx", help="Upload a WAV file to /radio/<sat> (uplink)")
    s_tx.add_argument("--satellite", required=True)
    s_tx.add_argument("--wav", required=True, help="Path to WAV file")
    s_tx.set_defaults(cmd="tx")

    return p


def main() -> int:
    args = build_parser().parse_args()
    if not args.base_url:
        raise SystemExit("Missing --base-url (or set ECHOFLARE_BASE_URL)")

    client = GroundTrackClient(args.base_url)

    try:
        if args.cmd == "list":
            for name in client.list_satellites():
                print(name)
            return 0

        if args.cmd == "status":
            st = client.get_status(args.satellite)
            print(json.dumps(st.raw, indent=2))
            return 0

        if args.cmd == "wait":
            st = client.wait_for_elevation(
                args.satellite,
                min_elevation_deg=args.min_elevation,
                timeout_s=args.timeout,
            )
            print(json.dumps(st.raw, indent=2))
            return 0

        if args.cmd == "rx":
            out = Path(args.out)
            client.download_radio_wav(args.satellite, out, seconds=args.seconds)
            print(str(out))
            return 0

        if args.cmd == "tx":
            resp = client.upload_radio_wav(args.satellite, Path(args.wav))
            print(resp)
            return 0

        raise SystemExit("Unknown command")

    except GroundTrackError as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    raise SystemExit(main())
