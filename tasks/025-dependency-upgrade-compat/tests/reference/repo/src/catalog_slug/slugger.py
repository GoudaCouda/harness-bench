"""Compatibility wrapper around the catalogue slug dependency."""

import re

from slugify import slugify


def make_slug(title, preserve_unicode=False, separator="-"):
    """Return the stable external key used by catalogue importers."""
    if not isinstance(title, str):
        raise ValueError("title must be a string")
    if not isinstance(separator, str) or separator not in {"-", "_"}:
        raise ValueError("separator must be '-' or '_'")
    normalized_title = re.sub(r"_+", " ", title)
    return slugify(
        normalized_title,
        allow_unicode=preserve_unicode,
        separator=separator,
    )
