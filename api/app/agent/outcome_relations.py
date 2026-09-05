"""Relation-typed outcome contracts.

The centre understands a closed set of relation *kinds*. Values come from the
request. Format-specific measurement (how to open a file, how to hash pixels)
lives in adapters below; a new domain adds an adapter, not a new planner case.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import zlib
from pathlib import Path
from typing import Any, Iterable, Sequence

RELATION_TYPES = frozenset(
    {
        "produced",
        "opens_as",
        "novel_vs_inputs",
        "preserves_originals",
        "count",
        "size",
        "contains_declared",
    }
)

_TRANSFORM_SIGNALS = re.compile(
    r"\b("
    r"add|apply|overlay|stamp|convert|transform|change|modify|update|"
    r"insert|replace|compress|shrink|split|merge|combine|reformat|"
    r"extract|export|annotate|mark|resize|rotate|crop|redact"
    r")\b",
    re.IGNORECASE,
)
_PRESERVE_SIGNALS = re.compile(
    r"\b(untouched|unchanged|without\s+modif|do\s+not\s+(?:modify|delete|overwrite)|"
    r"remains?\s+untouched|original\s+(?:file\s+)?(?:remains?|stays?))\b",
    re.IGNORECASE,
)
_SIZE_LIMIT = re.compile(
    r"(?:smaller\s+than|less\s+than|under|below|at\s+most|no\s+more\s+than|"
    r"max(?:imum)?)\s+(\d+(?:\.\d+)?)\s*"
    r"(k(?:i)?b|m(?:i)?b|g(?:i)?b|bytes?|b)\b",
    re.IGNORECASE,
)
_SIZE_UNITS = {
    "b": 1,
    "byte": 1,
    "bytes": 1,
    "kb": 1000,
    "kib": 1024,
    "mb": 1000 * 1000,
    "mib": 1024 * 1024,
    "gb": 1000 * 1000 * 1000,
    "gib": 1024 * 1024 * 1024,
}

_ROLE_MAGIC: dict[str, tuple[bytes, ...]] = {
    "image": (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"RIFF"),
    "document": (b"%PDF",),
    "spreadsheet": (b"PK",),
    "presentation": (b"PK",),
    "archive": (b"PK",),
    "text": (),
    "json": (),
}

def criteria_mapping(raw: Any) -> dict[str, Any]:
    """Normalise stored or planned criteria to a mapping."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        return {"text": raw.strip()}
    return {"text": str(raw).strip()} if str(raw).strip() else {}


def criteria_text(raw: Any) -> str:
    mapping = criteria_mapping(raw)
    text = str(mapping.get("text") or mapping.get("criteria") or "").strip()
    if text:
        return text
    relations = mapping.get("relations")
    if isinstance(relations, list) and relations:
        return json.dumps({"relations": relations}, default=str)
    return ""


def has_contract(raw: Any) -> bool:
    mapping = criteria_mapping(raw)
    if criteria_text(raw):
        return True
    relations = mapping.get("relations")
    if isinstance(relations, list) and relations:
        return True
    return any(
        mapping.get(key) not in (None, "", [])
        for key in ("expected_artifact_count", "artifact_count", "expected_outputs")
    )


def declared_count(raw: Any) -> int | None:
    mapping = criteria_mapping(raw)
    for key in ("expected_artifact_count", "artifact_count", "expected_outputs"):
        value = mapping.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            parsed = int(value.strip())
            if parsed > 0:
                return parsed
    for rel in explicit_relations(raw):
        if rel.get("type") == "count":
            equals = rel.get("equals")
            if isinstance(equals, int) and equals > 0:
                return equals
    return None


def explicit_relations(raw: Any) -> list[dict[str, Any]]:
    mapping = criteria_mapping(raw)
    items = mapping.get("relations")
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or item.get("kind") or "").strip()
        if kind in RELATION_TYPES:
            out.append({**item, "type": kind})
    return out


def _combined_text(raw: Any, instruction: str) -> str:
    return f"{criteria_text(raw)} {instruction or ''}".strip()


def infer_relations(
    raw: Any,
    *,
    instruction: str = "",
    has_inputs: bool = False,
) -> list[dict[str, Any]]:
    """Fill relation kinds from explicit criteria, then from request wording."""
    found = list(explicit_relations(raw))
    seen = {str(item.get("type")) for item in found}
    mapping = criteria_mapping(raw)
    text = _combined_text(raw, instruction)

    def _add(kind: str, **extra: Any) -> None:
        if kind in seen:
            return
        seen.add(kind)
        found.append({"type": kind, **extra})

    if has_inputs and _TRANSFORM_SIGNALS.search(text):
        _add("novel_vs_inputs")
    if _PRESERVE_SIGNALS.search(text) or mapping.get("preserve_originals") is True:
        _add("preserves_originals")
    count = declared_count(raw)
    if count:
        _add("count", equals=count)
    limit = max_size_bytes(text)
    if limit is not None:
        _add("size", max_bytes=limit)
    return found


def max_size_bytes(text: str) -> int | None:
    match = _SIZE_LIMIT.search(text or "")
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).lower()
    factor = _SIZE_UNITS.get(unit)
    if factor is None:
        return None
    return int(amount * factor)


def file_bytes_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 64), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_fingerprint(path: Path) -> tuple[str, str]:
    """Return (method, digest). Image adapters hash raster content when possible."""
    suffix = path.suffix.lower()
    if suffix == ".png":
        raster = _png_raster_digest(path)
        if raster:
            return "png_raster", raster
    return "sha256", file_bytes_hash(path)


def files_same_content(left: Path, right: Path) -> bool | None:
    """True/False when measurable; None when the comparison is uncertain."""
    try:
        if not left.is_file() or not right.is_file():
            return None
        if file_bytes_hash(left) == file_bytes_hash(right):
            return True
        left_method, left_digest = content_fingerprint(left)
        right_method, right_digest = content_fingerprint(right)
        if left_method == right_method:
            return left_digest == right_digest
        return False
    except OSError:
        return None


def opens_as_role(path: Path, role: str) -> bool | None:
    role = (role or "").strip().lower()
    if not role:
        return None
    try:
        header = path.read_bytes()[:16]
    except OSError:
        return None
    if role == "text":
        try:
            path.read_text(encoding="utf-8")
            return True
        except (OSError, UnicodeDecodeError):
            return False
    if role == "json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
            return True
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
    magics = _ROLE_MAGIC.get(role)
    if magics is None:
        return None
    if not magics:
        return True
    return any(header.startswith(magic) for magic in magics)


def extract_text(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
    return None


def _png_raster_digest(path: Path) -> str | None:
    """Hash reconstructed PNG pixels. Adapter; other image types fall back."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    offset = 8
    width = height = bit_depth = color_type = None
    idat = bytearray()
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        ctype = data[offset + 4 : offset + 8]
        start = offset + 8
        end = start + length
        if end + 4 > len(data):
            return None
        chunk = data[start:end]
        if ctype == b"IHDR" and length >= 13:
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif ctype == b"IDAT":
            idat.extend(chunk)
        elif ctype == b"IEND":
            break
        offset = end + 4
    if not width or not height or bit_depth != 8 or color_type not in {2, 6}:
        return None
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error:
        return None
    bpp = 3 if color_type == 2 else 4
    stride = width * bpp
    expected = height * (stride + 1)
    if len(raw) < expected:
        return None
    rows: list[bytes] = []
    prev = bytes(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        scan = raw[cursor + 1 : cursor + 1 + stride]
        cursor += 1 + stride
        recon = _unfilter_png(filter_type, scan, prev, bpp)
        if recon is None:
            return None
        rows.append(recon)
        prev = recon
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row)
    return digest.hexdigest()


def _unfilter_png(
    filter_type: int, scan: bytes, prev: bytes, bpp: int
) -> bytes | None:
    out = bytearray(len(scan))
    if filter_type == 0:
        return bytes(scan)
    if filter_type == 1:
        for i, value in enumerate(scan):
            left = out[i - bpp] if i >= bpp else 0
            out[i] = (value + left) & 0xFF
        return bytes(out)
    if filter_type == 2:
        for i, value in enumerate(scan):
            out[i] = (value + prev[i]) & 0xFF
        return bytes(out)
    if filter_type == 3:
        for i, value in enumerate(scan):
            left = out[i - bpp] if i >= bpp else 0
            out[i] = (value + ((left + prev[i]) // 2)) & 0xFF
        return bytes(out)
    if filter_type == 4:
        for i, value in enumerate(scan):
            left = out[i - bpp] if i >= bpp else 0
            up = prev[i]
            up_left = prev[i - bpp] if i >= bpp else 0
            out[i] = (value + _paeth(left, up, up_left)) & 0xFF
        return bytes(out)
    return None


def _paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    distances = (abs(estimate - left), abs(estimate - up), abs(estimate - up_left))
    return (left, up, up_left)[distances.index(min(distances))]


def evaluate_relations(
    relations: Sequence[dict[str, Any]],
    *,
    produced: Sequence[Path],
    known_inputs: Sequence[Path] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate each relation. Status is pass / fail / uncertain."""
    inputs = [Path(p) for p in (known_inputs or []) if Path(p).is_file()]
    outputs = [Path(p) for p in produced if Path(p).is_file()]
    reports: list[dict[str, Any]] = []
    for rel in relations:
        kind = str(rel.get("type") or "")
        reports.append(_evaluate_one(kind, rel, outputs=outputs, inputs=inputs))
    return reports


def _evaluate_one(
    kind: str,
    rel: dict[str, Any],
    *,
    outputs: list[Path],
    inputs: list[Path],
) -> dict[str, Any]:
    if kind == "produced":
        if outputs:
            return _pass(kind, f"{len(outputs)} new artifact(s)")
        return _fail(kind, "no new artifact was produced")
    if kind == "count":
        expected = rel.get("equals")
        if not isinstance(expected, int) or expected <= 0:
            return _uncertain(kind, "count was not a positive integer")
        if len(outputs) == expected:
            return _pass(kind, f"count={len(outputs)}")
        return _fail(kind, f"count={len(outputs)}; contract requires {expected}")
    if kind == "size":
        limit = rel.get("max_bytes")
        if not isinstance(limit, int) or limit <= 0:
            return _uncertain(kind, "size ceiling was not measurable")
        for path in outputs:
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > limit:
                return _fail(
                    kind,
                    f"{path.name} is {size} bytes; contract requires under {limit} bytes",
                )
        return _pass(kind, f"all artifacts under {limit} bytes")
    if kind == "opens_as":
        role = str(rel.get("as") or rel.get("role") or "").strip()
        if not role:
            return _uncertain(kind, "no role declared")
        measured = False
        for path in outputs:
            verdict = opens_as_role(path, role)
            if verdict is None:
                continue
            measured = True
            if not verdict:
                return _fail(kind, f"{path.name} does not open as {role}")
        if not measured:
            return _uncertain(kind, f"could not measure role {role}")
        return _pass(kind, f"opens as {role}")
    if kind == "preserves_originals":
        if not inputs:
            return _uncertain(kind, "no inputs to compare")
        missing = [p.name for p in inputs if not p.is_file()]
        if missing:
            return _fail(kind, f"inputs missing: {missing}")
        return _pass(kind, "inputs still present")
    if kind == "novel_vs_inputs":
        if not outputs:
            return _fail(kind, "no outputs to compare to inputs")
        if not inputs:
            return _uncertain(kind, "no inputs to compare")
        same = 0
        uncertain = 0
        for out in outputs:
            matched = False
            unknown = False
            for src in inputs:
                verdict = files_same_content(out, src)
                if verdict is True:
                    matched = True
                    break
                if verdict is None:
                    unknown = True
            if matched:
                same += 1
            elif unknown:
                uncertain += 1
        if same:
            return _fail(
                kind,
                f"{same} output(s) are unchanged relative to the inputs",
            )
        if uncertain and same == 0 and uncertain == len(outputs):
            return _uncertain(kind, "could not compare output content to inputs")
        return _pass(kind, "outputs differ from inputs")
    if kind == "contains_declared":
        tokens = [str(t) for t in (rel.get("tokens") or []) if str(t).strip()]
        if not tokens:
            return _uncertain(kind, "no declared tokens")
        readable = [extract_text(path) for path in outputs]
        texts = [text for text in readable if text is not None]
        if not texts:
            return _uncertain(kind, "declared tokens are not readable in the artifacts")
        blob = "\n".join(texts)
        missing = [token for token in tokens if token not in blob]
        if missing:
            return _fail(kind, f"missing declared tokens: {missing}")
        return _pass(kind, "declared tokens present")
    return _uncertain(kind, f"unknown relation {kind!r}")


def _pass(kind: str, reason: str) -> dict[str, Any]:
    return {"type": kind, "status": "pass", "reason": reason}


def _fail(kind: str, reason: str) -> dict[str, Any]:
    return {"type": kind, "status": "fail", "reason": reason}


def _uncertain(kind: str, reason: str) -> dict[str, Any]:
    return {"type": kind, "status": "uncertain", "reason": reason}


def summarize_reports(reports: Iterable[dict[str, Any]]) -> tuple[str, str, bool]:
    """Return (method, reason, partial) for the worst report."""
    items = list(reports)
    failed = [item for item in items if item.get("status") == "fail"]
    uncertain = [item for item in items if item.get("status") == "uncertain"]
    if failed:
        first = failed[0]
        return (
            "relation_unmet",
            str(first.get("reason") or "relation unmet"),
            first.get("type") != "produced",
        )
    if uncertain:
        first = uncertain[0]
        return (
            "uncertain",
            str(first.get("reason") or "relation could not be measured"),
            False,
        )
    return ("relations", "all relations passed", False)
