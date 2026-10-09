"""Downstream caller whose public use of :func:`make_slug` must remain stable."""

from __future__ import annotations

from collections.abc import Iterable

from .slugger import make_slug


def prepare_feed_rows(
    rows: Iterable[dict[str, object]],
    *,
    preserve_unicode: bool = False,
    separator: str = "-",
) -> list[dict[str, object]]:
    """Add deterministic URL keys without mutating source feed rows."""
    prepared: list[dict[str, object]] = []
    for row in rows:
        copied = dict(row)
        copied["url_key"] = make_slug(
            copied.get("title"),
            preserve_unicode=preserve_unicode,
            separator=separator,
        )
        prepared.append(copied)
    return prepared
