"""Helpers shared by document parsers."""

from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO, Union

PathLike = Union[str, Path]
Readable = Union[PathLike, BinaryIO, bytes]


def normalize_filename(filename: str | None) -> str | None:
    if filename is None:
        return None
    name = Path(str(filename)).name.strip()
    return name or None


def read_bytes(source: Readable) -> bytes:
    if isinstance(source, Path):
        return source.read_bytes()
    if isinstance(source, str):
        return Path(source).read_bytes()
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    data = source.read()
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


def as_binary_buffer(source: Readable) -> io.BytesIO:
    return io.BytesIO(read_bytes(source))
