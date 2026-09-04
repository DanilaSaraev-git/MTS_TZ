"""Local, provider-independent helpers for agent-led review."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
from pathlib import Path

__version__ = "0.1.0"
RESOURCES = Path(__file__).parent / "resources"


class ReviewError(ValueError):
    """An input or contract error suitable for a user-facing diagnostic."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReviewError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ReviewError(f"Invalid JSON: {value}")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewError(f"Cannot read JSON {path.name}: {exc}") from exc


def write_json(path: Path, value) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def within(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ReviewError("Snapshot paths must be relative")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()) or target == root.resolve():
        raise ReviewError(f"Snapshot path escapes run: {relative}")
    return target
