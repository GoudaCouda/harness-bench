def select_wheel(target, assets):
    """Broken legacy behavior: choose the first vaguely matching wheel."""
    project = target["project"].replace("-", "_")
    for asset in assets:
        if project in asset["filename"] and asset["filename"].endswith(".whl"):
            return {
                "decision": "select",
                "filename": asset["filename"],
                "sha256": asset["sha256"],
                "size": asset["size"],
                "matched_tag": None,
                "build": None,
            }
    return {
        "decision": "no_compatible",
        "filename": None,
        "sha256": None,
        "size": None,
        "matched_tag": None,
        "build": None,
    }
