def plan_version_sync(release_tag, previous_tag, manifests):
    """Broken implementation: one spelling is copied without validation."""
    target = release_tag.lstrip("v")
    return {"release": target, "previous": previous_tag.lstrip("v"), "prerelease": "-" in target, "changes": [
        {"path": item["path"], "ecosystem": item["ecosystem"], "from": item["current"], "to": target, "action": "update", "publish": item["publish"]}
        for item in manifests
    ]}
