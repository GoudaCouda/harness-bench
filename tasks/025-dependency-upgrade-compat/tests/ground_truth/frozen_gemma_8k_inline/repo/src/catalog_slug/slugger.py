from slugify import slugify


def make_slug(title, preserve_unicode=False, separator="-"):
    """Return the stable external key used by catalogue importers."""
    if not isinstance(title, str):
        raise ValueError("title must be a string")
    if separator not in ("-", "_"):
        raise ValueError("separator must be '-' or '_'")

    return slugify(title.replace("_", " "), separator=separator, allow_unicode=preserve_unicode)
