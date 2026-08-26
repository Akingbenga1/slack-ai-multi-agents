"""Portable tldr pages SQLite store — search + upstream rebuild."""

from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1"
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "for",
        "of",
        "and",
        "or",
        "in",
        "on",
        "with",
        "from",
        "into",
        "how",
        "do",
        "i",
        "my",
    }
)


@dataclass(frozen=True)
class TldrHit:
    command: str
    platform: str
    description: str
    score: float
    body: str = ""


def detect_platform() -> str:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "osx"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("freebsd"):
        return "freebsd"
    if sys.platform.startswith("netbsd"):
        return "netbsd"
    if sys.platform.startswith("openbsd"):
        return "openbsd"
    if sys.platform.startswith("sunos"):
        return "sunos"
    return "linux"


def search_platforms() -> tuple[str, ...]:
    return ("common", detect_platform())


def ensure_tldr_installed() -> None:
    try:
        import tldr  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tldr"])


def cache_dir() -> Path:
    import tldr

    return Path(tldr.get_cache_dir()) / "pages"


def update_upstream_cache() -> None:
    subprocess.check_call([sys.executable, "-m", "tldr", "--update"])


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS]


def page_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("# ").strip()
    return ""


def page_description(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            return stripped.lstrip("> ").strip()
    return ""


def contains_token(haystack: str, token: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack) is not None


def score_page(tokens: list[str], command: str, description: str, body: str) -> float:
    """OR-match query tokens and rank hits; drop body-only weak matches.

    - Any token may contribute (OR), unlike the old all-tokens-required rule.
    - Name/description hits are required for a non-zero score (filters junk).
    - More matching tokens and description coverage rank higher.
    """
    if not tokens:
        return 0.0
    desc = description.lower()
    body_l = body.lower()
    name = command.lower().replace("-", " ")
    cmd = command.lower()

    matched = 0
    name_hits = 0
    desc_hits = 0
    body_hits = 0
    score = 0.0

    for token in tokens:
        in_name = contains_token(name, token) or token in cmd
        in_desc = contains_token(desc, token)
        in_body = contains_token(body_l, token)
        if not (in_name or in_desc or in_body):
            continue
        matched += 1
        if in_name:
            name_hits += 1
            score += 3.0
        if in_desc:
            desc_hits += 1
            score += 2.0
        elif in_body and not in_name:
            body_hits += 1
            score += 0.5

    # Filter: ignore pages that only match deep example text.
    if name_hits == 0 and desc_hits == 0:
        return 0.0
    if matched == 0:
        return 0.0

    # Ranking boosts: coverage of the query + multi-token agreement.
    coverage = matched / len(tokens)
    score += coverage * 5.0
    if matched >= 2:
        score += 2.0 * (matched - 1)
    if desc_hits >= 2:
        score += 3.0
    if name_hits >= 1 and desc_hits >= 1:
        score += 1.5

    # Soft filter for long queries: a single weak token match ranks out later,
    # but very weak single body-adjacent noise is already excluded above.
    if len(tokens) >= 3 and matched == 1 and name_hits == 0 and desc_hits == 1:
        # Keep, but do not boost further — common-word-only hits stay low.
        pass

    return score


def connect_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS pages_fts;
        DROP TABLE IF EXISTS pages;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE pages (
            id INTEGER PRIMARY KEY,
            command TEXT NOT NULL,
            platform TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en',
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL,
            UNIQUE (language, platform, command)
        );

        CREATE VIRTUAL TABLE pages_fts USING fts5(
            command,
            title,
            description,
            body,
            content='pages',
            content_rowid='id'
        );
        """
    )


def iter_page_rows(pages_root: Path) -> list[tuple[str, str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str, str]] = []
    if not pages_root.is_dir():
        return rows

    for platform_dir in sorted(p for p in pages_root.iterdir() if p.is_dir()):
        platform = platform_dir.name
        for path in sorted(platform_dir.glob("*.md")):
            body = path.read_text(encoding="utf-8", errors="ignore")
            rows.append(
                (
                    path.stem,
                    platform,
                    "en",
                    page_title(body),
                    page_description(body),
                    body,
                )
            )
    return rows


def rebuild_db_from_upstream(db_path: Path) -> int:
    """Pull upstream tldr pages and atomically rewrite the SQLite DB."""
    ensure_tldr_installed()
    update_upstream_cache()
    pages_root = cache_dir()
    rows = iter_page_rows(pages_root)
    if not rows:
        raise RuntimeError(f"No tldr pages found under {pages_root}")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        prefix="tldr_pages_",
        suffix=".db",
        dir=str(db_path.parent),
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        conn = connect_db(tmp_path)
        try:
            init_schema(conn)
            conn.executemany(
                """
                INSERT INTO pages (command, platform, language, title, description, body)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.execute(
                """
                INSERT INTO pages_fts(rowid, command, title, description, body)
                SELECT id, command, title, description, body FROM pages
                """
            )
            now = datetime.now(timezone.utc).isoformat()
            conn.executemany(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                [
                    ("schema_version", SCHEMA_VERSION),
                    ("built_at", now),
                    ("source", "tldr upstream cache"),
                    ("page_count", str(len(rows))),
                ],
            )
            conn.commit()
        finally:
            conn.close()
        tmp_path.replace(db_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    return len(rows)


def search_db(
    query: str,
    *,
    db_path: Path,
    limit: int = 15,
    platforms: tuple[str, ...] | None = None,
) -> list[TldrHit]:
    """Search the portable SQLite DB (read-only; no upstream refresh)."""
    tokens = tokenize(query)
    if not tokens:
        return []

    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"tldr SQLite DB not found: {path}")

    plats = platforms or search_platforms()
    placeholders = ",".join("?" for _ in plats)
    conn = connect_db(path)
    try:
        cur = conn.execute(
            f"""
            SELECT command, platform, description, body
            FROM pages
            WHERE platform IN ({placeholders})
            """,
            plats,
        )
        hits: list[TldrHit] = []
        for row in cur:
            score = score_page(tokens, row["command"], row["description"], row["body"])
            if score <= 0:
                continue
            hits.append(
                TldrHit(
                    command=row["command"],
                    platform=row["platform"],
                    description=row["description"] or "(no description)",
                    score=score,
                    body=row["body"] or "",
                )
            )
    finally:
        conn.close()

    hits.sort(key=lambda h: (-h.score, h.command))
    return hits[:limit]
