# Echoflare helpers

This folder contains a minimal, self-contained toolkit to:

- Decode 2-address AX.25 UI frames (no digipeaters)
- Decode Echoflare `TL` telemetry payloads
- Build signed telecommands (HMAC-SHA256) for:
  - `0x5500` Set Message of the Day
  - `0x5533` Trigger SSTV (ROBOT36)

It **does not** demodulate G3RUH/9600baud from RF/audio. Use your preferred demodulator (e.g. `gr-satellites`) to obtain *raw AX.25 frames*, then feed those bytes into this parser.

## CLI usage

From the workspace root:

- Decode an AX.25 frame:

  - `python -m echoflare.cli decode-ax25 --hex <hex>`

- Decode telemetry (`TL`) from an AX.25 frame:

  - `python -m echoflare.cli decode-telemetry --ax25 --file downlink_frame.bin`

- Build Set-MotD telecommand (wrap in AX.25 UI frame):

  - `python -m echoflare.cli build-motd --sequence <SEQ> --motd "j_m0 was here" --ax25 --out uplink_frame.bin --print-hex`

- Build SSTV telecommand (wrap in AX.25 UI frame):

  - `python -m echoflare.cli build-sstv --sequence <SEQ> --ax25 --out uplink_frame.bin --print-hex`

### Sequence numbers

Use the `sequence` value from the latest successfully decoded telemetry. The satellite increments its internal sequence counter by 1 after processing any **valid** telecommand.

If your MotD command is accepted, use the *next expected sequence* for SSTV.

## GroundTrack site API helper

If you want to script the same API that the browser UI uses, see:

- [groundtrack_api.py](groundtrack_api.py) (library)
- [groundtrack_cli.py](groundtrack_cli.py) (CLI)

It talks to:

- `GET /satellite` (list)
- `GET /satellite/<id>` (status JSON)
- `GET /radio/<id>` (live RX audio)
- `POST /radio/<id>` (multipart upload of a TX `.wav`)

Example:

- `python -m echoflare.groundtrack_cli --base-url https://<host> list`
- `python -m echoflare.groundtrack_cli --base-url https://<host> status --satellite <name>`
- `python -m echoflare.groundtrack_cli --base-url https://<host> rx --satellite <name> --out rx.wav --seconds 30`

## Mission helper (telemetry -> MotD -> SSTV)

There is also an end-to-end helper that:

1) waits for a good pass (min elevation)
2) captures RX audio and demods TL telemetry to get the current command sequence
3) transmits MotD (`j_m0 was here` by default)
4) transmits the SSTV trigger
5) captures SSTV downlink audio into a `.wav`

Run:

- `python -m echoflare.mission_cli --base-url https://ground-control.csokavar.hu --satellite Echoflare --min-elevation 10`

It saves artifacts under `echoflare_runs/`.
