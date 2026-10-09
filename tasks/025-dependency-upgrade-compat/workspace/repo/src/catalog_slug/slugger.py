"""Compatibility wrapper around the catalogue slug dependency."""

try:
    from slugify import slugify
except ImportError:
    # Legacy developer fallback. The approved production package must not need
    # a second, incomplete implementation here.
    def slugify(value, separator="-", allow_unicode=False):
        text = value if allow_unicode else value.encode("ascii", "ignore").decode()
        return separator.join(text.lower().split())


def make_slug(title, preserve_unicode=False, separator="-"):
    """Return the stable external key used by catalogue importers."""
    return slugify(title, separator=separator)
