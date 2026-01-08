from __future__ import annotations

import json
import mimetypes
import os
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import wave


class GroundTrackError(RuntimeError):
    pass


def _join(base_url: str, path: str) -> str:
    base = base_url.rstrip("/") + "/"
    return urllib.parse.urljoin(base, path.lstrip("/"))


def _http_get(url: str, *, timeout_s: float = 30.0, headers: Optional[dict[str, str]] = None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise GroundTrackError(f"GET {url} failed: {e.code} {e.reason}; {body}") from e
    except urllib.error.URLError as e:
        raise GroundTrackError(f"GET {url} failed: {e.reason}") from e


def _encode_multipart_file(field_name: str, file_path: Path, *, filename: Optional[str] = None) -> tuple[bytes, str]:
    boundary = f"----echoflare-{int(time.time()*1000)}"

    filename = filename or file_path.name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    file_bytes = file_path.read_bytes()

    parts: list[bytes] = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        (
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
    )
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(parts)
    return body, boundary


def _http_post_multipart(url: str, *, file_field: str, file_path: Path, timeout_s: float = 60.0) -> tuple[int, str]:
    body, boundary = _encode_multipart_file(file_field, file_path)

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = getattr(resp, "status", 200)
            text = resp.read().decode("utf-8", errors="replace")
            return int(status), text
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise GroundTrackError(f"POST {url} failed: {e.code} {e.reason}; {text}") from e
    except urllib.error.URLError as e:
        raise GroundTrackError(f"POST {url} failed: {e.reason}") from e


@dataclass(frozen=True)
class SatelliteStatus:
    raw: dict[str, Any]

    @property
    def name(self) -> Optional[str]:
        v = self.raw.get("name")
        return str(v) if v is not None else None

    @property
    def elevation_deg(self) -> Optional[float]:
        v = self.raw.get("elevation_deg")
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def downlink_mhz(self) -> Optional[float]:
        v = self.raw.get("downlink_mhz")
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def doppler_hz(self) -> Optional[float]:
        v = self.raw.get("doppler_hz")
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None


class GroundTrackClient:
    """Client for the GroundTrack site API used by the web UI.

    The JS bundle uses only these endpoints:
      - GET /satellite            -> list of satellite IDs/names
      - GET /satellite/<id>       -> status JSON (updated every ~1s)
      - GET /radio/<id>           -> live audio stream
      - POST /radio/<id> (multipart 'file') -> uplink WAV upload
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def list_satellites(self) -> list[str]:
        url = _join(self.base_url, "/satellite")
        data = json.loads(_http_get(url).decode("utf-8", errors="replace"))
        if not isinstance(data, list):
            raise GroundTrackError(f"Unexpected /satellite response type: {type(data)}")
        return [str(x) for x in data]

    def get_status(self, satellite_id: str) -> SatelliteStatus:
        sat = urllib.parse.quote(satellite_id, safe="")
        url = _join(self.base_url, f"/satellite/{sat}")
        raw = json.loads(_http_get(url).decode("utf-8", errors="replace"))
        if not isinstance(raw, dict):
            raise GroundTrackError(f"Unexpected /satellite/<id> response type: {type(raw)}")
        return SatelliteStatus(raw=raw)

    def wait_for_elevation(
        self,
        satellite_id: str,
        *,
        min_elevation_deg: float = 10.0,
        poll_s: float = 1.0,
        timeout_s: float = 15 * 60.0,
    ) -> SatelliteStatus:
        start = time.time()
        last: Optional[SatelliteStatus] = None
        while True:
            if time.time() - start > timeout_s:
                raise GroundTrackError(
                    f"Timed out waiting for elevation >= {min_elevation_deg} deg (last={last.elevation_deg if last else None})"
                )

            st = self.get_status(satellite_id)
            last = st
            if st.elevation_deg is not None and st.elevation_deg >= min_elevation_deg:
                return st
            time.sleep(poll_s)

    def download_radio_wav(
        self,
        satellite_id: str,
        out_path: Path,
        *,
        seconds: float = 30.0,
        timeout_s: float = 10.0,
        chunk_size: int = 64 * 1024,
    ) -> Path:
        """Capture the live /radio/<id> stream for roughly `seconds`.

        The GroundTrack /radio endpoint typically returns a WAV stream. Some deployments
        close the connection after ~tens of seconds even if we requested longer.

        This function:
        - reconnects as needed until the deadline
        - extracts and concatenates PCM samples
        - writes a *valid* WAV header (so decoders/demodulators behave)
        """

        sat = urllib.parse.quote(satellite_id, safe="")
        url = _join(self.base_url, f"/radio/{sat}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + float(seconds)

        def _parse_wav_header_prefix(buf: bytes) -> Optional[tuple[int, int, int, int, int]]:
            """Return (channels, sample_rate, sample_width_bytes, riff_offset, data_offset).

            Searches `buf` for a RIFF/WAVE header and parses fmt/data chunks if present.
            Returns None if no complete header could be parsed from the available bytes.
            """

            if len(buf) < 12:
                return None

            # Some servers may send a live stream where the client attaches mid-flow,
            # or where the RIFF header arrives after a few bytes. Search within buffer.
            riff = buf.find(b"RIFF")
            if riff < 0 or riff + 12 > len(buf):
                return None
            if buf[riff + 8 : riff + 12] != b"WAVE":
                return None

            offset = riff + 12
            channels: Optional[int] = None
            sample_rate: Optional[int] = None
            bits_per_sample: Optional[int] = None
            data_offset: Optional[int] = None

            # Walk chunks until we find fmt + data. We only scan within the prefix.
            while offset + 8 <= len(buf):
                chunk_id = buf[offset : offset + 4]
                chunk_size = struct.unpack_from("<I", buf, offset + 4)[0]
                chunk_data = offset + 8
                next_chunk = chunk_data + chunk_size
                if next_chunk > len(buf):
                    return None

                if chunk_id == b"fmt ":
                    if chunk_size < 16:
                        raise GroundTrackError("Invalid WAV fmt chunk")
                    audio_format, ch, sr = struct.unpack_from("<HHI", buf, chunk_data)
                    if audio_format != 1:
                        raise GroundTrackError(f"Unsupported WAV format: {audio_format} (expected PCM=1)")
                    channels = int(ch)
                    sample_rate = int(sr)
                    bits_per_sample = int(struct.unpack_from("<H", buf, chunk_data + 14)[0])
                elif chunk_id == b"data":
                    data_offset = chunk_data
                    break

                # Chunks are word-aligned.
                offset = next_chunk + (chunk_size & 1)

            if channels is None or sample_rate is None or bits_per_sample is None or data_offset is None:
                return None

            if bits_per_sample % 8 != 0:
                raise GroundTrackError(f"Unsupported bits/sample: {bits_per_sample}")
            sample_width = bits_per_sample // 8
            return channels, sample_rate, sample_width, riff, data_offset

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)

            params: Optional[tuple[int, int, int]] = None  # (channels, sample_rate, sampwidth)
            wout: Optional[wave.Wave_write] = None
            try:
                while time.time() < deadline:
                    req = urllib.request.Request(url, method="GET")
                    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                        # Read enough data to reliably parse RIFF chunks, even if fmt/data
                        # lands beyond the first few KB.
                        buf = bytearray()
                        header_limit = 256 * 1024
                        while len(buf) < header_limit:
                            chunk = resp.read(min(chunk_size, header_limit - len(buf)))
                            if not chunk:
                                break
                            buf.extend(chunk)
                            parsed = _parse_wav_header_prefix(bytes(buf))
                            if parsed is not None:
                                ch, sr, sw, riff_off, data_off = parsed
                                if params is None:
                                    params = (ch, sr, sw)
                                    wout = wave.open(str(out_path), "wb")
                                    wout.setnchannels(ch)
                                    wout.setframerate(sr)
                                    wout.setsampwidth(sw)
                                else:
                                    if params != (ch, sr, sw):
                                        raise GroundTrackError(
                                            f"/radio WAV params changed mid-capture: got {(ch, sr, sw)} expected {params}"
                                        )

                                # Write PCM already in buffer after the data chunk header.
                                if data_off < len(buf):
                                    wout.writeframesraw(bytes(buf[data_off:]))
                                buf.clear()
                                break

                        if buf:
                            # No WAV header detected. Fall back to treating bytes as raw PCM.
                            # The GroundTrack captures we demod expect 48kHz, mono, 16-bit.
                            if params is None:
                                params = (1, 48000, 2)
                                wout = wave.open(str(out_path), "wb")
                                wout.setnchannels(params[0])
                                wout.setframerate(params[1])
                                wout.setsampwidth(params[2])
                            wout.writeframesraw(bytes(buf))
                            buf.clear()

                        while time.time() < deadline:
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            # If the server starts each connection with a fresh WAV header,
                            # we need to skip it; otherwise just treat as PCM.
                            parsed = _parse_wav_header_prefix(chunk)
                            if parsed is not None:
                                ch, sr, sw, riff_off, data_off = parsed
                                if params is None:
                                    params = (ch, sr, sw)
                                    wout = wave.open(str(out_path), "wb")
                                    wout.setnchannels(ch)
                                    wout.setframerate(sr)
                                    wout.setsampwidth(sw)
                                if params != (ch, sr, sw):
                                    raise GroundTrackError(
                                        f"/radio WAV params changed mid-capture: got {(ch, sr, sw)} expected {params}"
                                    )
                                if data_off < len(chunk):
                                    wout.writeframesraw(chunk[data_off:])
                            else:
                                if params is None:
                                    params = (1, 48000, 2)
                                    wout = wave.open(str(out_path), "wb")
                                    wout.setnchannels(params[0])
                                    wout.setframerate(params[1])
                                    wout.setsampwidth(params[2])
                                wout.writeframesraw(chunk)
            finally:
                if wout is not None:
                    wout.close()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
            raise GroundTrackError(f"GET {url} failed: {e.code} {e.reason}; {body}") from e
        except urllib.error.URLError as e:
            raise GroundTrackError(f"GET {url} failed: {e.reason}") from e

        except wave.Error as e:
            raise GroundTrackError(f"Failed to write WAV output: {e}") from e

        return out_path

    def upload_radio_wav(self, satellite_id: str, wav_path: Path) -> str:
        if wav_path.suffix.lower() != ".wav":
            raise ValueError("Upload expects a .wav file")

        sat = urllib.parse.quote(satellite_id, safe="")
        url = _join(self.base_url, f"/radio/{sat}")
        status, text = _http_post_multipart(url, file_field="file", file_path=wav_path)
        # The web UI treats any 2xx as success and shows text.
        if status < 200 or status >= 300:
            raise GroundTrackError(f"Upload failed: HTTP {status}; {text}")
        return text


def base_url_from_env() -> Optional[str]:
    return os.environ.get("ECHOFLARE_BASE_URL")
