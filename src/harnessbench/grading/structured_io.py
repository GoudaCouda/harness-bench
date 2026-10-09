"""Fail-closed readers for candidate-authored structured artifacts."""

from __future__ import annotations

import csv
import html
import io
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


class StructuredDataError(ValueError):
    """Candidate data is ambiguous, malformed, or outside the public schema."""


def _reject_constant(value: str) -> None:
    raise StructuredDataError(f"non-standard JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StructuredDataError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_loads(text: str) -> Any:
    """Parse standards-compliant JSON while rejecting duplicate object keys."""
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except StructuredDataError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise StructuredDataError(f"invalid JSON: {type(exc).__name__}") from exc


def read_text_file(path: Path, *, max_bytes: int) -> str:
    """Read one bounded, regular UTF-8 file without following a final symlink."""
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > max_bytes:
            raise StructuredDataError("file is absent, linked, or oversized")
        value = path.read_text(encoding="utf-8")
    except StructuredDataError:
        raise
    except (OSError, UnicodeError) as exc:
        raise StructuredDataError(f"file is unreadable: {type(exc).__name__}") from exc
    if "\x00" in value:
        raise StructuredDataError("file contains a NUL byte")
    return value


def read_json_file(path: Path, *, max_bytes: int) -> Any:
    return strict_json_loads(read_text_file(path, max_bytes=max_bytes))


def read_strict_csv(
    path: Path,
    *,
    header: Iterable[str],
    max_bytes: int,
    allow_utf8_bom: bool = False,
) -> list[dict[str, str]]:
    """Read an exact-width CSV; both row underflow and overflow are errors."""
    expected = list(header)
    text = read_text_file(path, max_bytes=max_bytes)
    if text.startswith("\ufeff"):
        if not allow_utf8_bom:
            raise StructuredDataError("CSV has an undeclared UTF-8 BOM")
        # A single document-leading BOM is transport metadata, not a cell.
        # Any additional or embedded control/format code point remains visible
        # to the caller's per-cell safety checks.
        text = text[1:]
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except (csv.Error, UnicodeError) as exc:
        raise StructuredDataError(f"invalid CSV: {type(exc).__name__}") from exc
    if not rows or rows[0] != expected or len(set(rows[0])) != len(rows[0]):
        raise StructuredDataError("CSV header does not match the exact schema")
    records: list[dict[str, str]] = []
    for index, row in enumerate(rows[1:], start=2):
        if len(row) != len(expected):
            raise StructuredDataError(
                f"CSV row {index} has {len(row)} cells; expected {len(expected)}"
            )
        records.append(dict(zip(expected, row)))
    return records


def contains_control_or_format(value: str) -> bool:
    """Return true for Unicode control/format code points, including BOM."""
    return any(unicodedata.category(character) in {"Cc", "Cf"} for character in value)


def spreadsheet_formula_text(value: str) -> bool:
    """Detect formula-like text fields after rejecting invisible prefixes.

    Callers should apply this only to text/identifier fields; signed numeric
    columns must first be parsed according to their public numeric schema.
    """
    if contains_control_or_format(value):
        return True
    return value.lstrip().startswith(("=", "+", "-", "@"))


def portable_identifier(value: str, *, max_length: int = 64) -> bool:
    """Validate a bounded ASCII identifier suitable for CSV/JSON joins."""
    if max_length < 1:
        raise ValueError("max_length must be positive")
    return bool(
        re.fullmatch(
            rf"[A-Za-z0-9][A-Za-z0-9._:-]{{0,{max_length - 1}}}",
            value,
        )
    )


_MARKDOWN_LINK = re.compile(r"!?\[([^\]\n]*)\]\([^\n)]*\)")
_MARKDOWN_REFERENCE_LINK = re.compile(r"!?\[([^\]\n]*)\]\[[^\]\n]*\]")
_HTML_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^>\n]{0,480})?/?>")


def markdown_visible_text(value: object) -> str:
    """Return conservative visible text for safety checks on Markdown.

    This is deliberately not a presentation renderer.  It removes common
    zero-width and formatting mechanisms that could split a sensitive word or
    action claim while preserving link labels, line boundaries, identifiers,
    and the text a reviewer would actually read.
    """
    text = unicodedata.normalize("NFKC", html.unescape(str(value)))
    text = _MARKDOWN_LINK.sub(lambda match: match.group(1), text)
    text = _MARKDOWN_REFERENCE_LINK.sub(lambda match: match.group(1), text)
    text = _HTML_TAG.sub("", text)
    text = re.sub(r"\\([\\`*{}\[\]()#+.!~>-])", r"\1", text)
    text = text.translate(str.maketrans("", "", "*`~"))

    visible: list[str] = []
    for character in text:
        category = unicodedata.category(character)
        if category == "Cf":
            continue
        if category == "Cc":
            visible.append(character if character in "\n\r\t" else " ")
            continue
        visible.append(character)
    return unicodedata.normalize("NFKC", "".join(visible))
