"""Tiny PNG writer for outcome-relation tests."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


def write_solid_png(path: Path, *, width: int = 4, height: int = 4, rgb: tuple[int, int, int] = (10, 20, 30)) -> Path:
    raw = bytearray()
    pixel = bytes(rgb)
    for _ in range(height):
        raw.append(0)
        raw.extend(pixel * width)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    def chunk(tag: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(tag + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", crc)

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    return path
