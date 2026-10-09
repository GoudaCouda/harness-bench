import re

PROJECT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+!]*")
TAG = re.compile(r"[A-Za-z0-9_]+")
SHA256 = re.compile(r"[0-9a-f]{64}")
BUILD = re.compile(r"[0-9]+[A-Za-z0-9_]*")


def _target(target):
    keys = {"project", "version", "supported_tags", "allow_yanked"}
    if not isinstance(target, dict) or set(target) != keys:
        raise ValueError("invalid target shape")
    project = target["project"]
    version = target["version"]
    tags = target["supported_tags"]
    if (
        not isinstance(project, str)
        or not PROJECT.fullmatch(project)
        or not isinstance(version, str)
        or not VERSION.fullmatch(version)
        or type(target["allow_yanked"]) is not bool
        or not isinstance(tags, list)
        or not tags
        or len(tags) > 10000
    ):
        raise ValueError("invalid target")
    ranking = {}
    for index, value in enumerate(tags):
        if not isinstance(value, str):
            raise ValueError("invalid supported tag")
        fields = value.split("-")
        if len(fields) != 3 or any(not TAG.fullmatch(field) for field in fields):
            raise ValueError("invalid supported tag")
        if value in ranking:
            raise ValueError("duplicate supported tag")
        ranking[value] = index
    return ranking


def _components(value):
    fields = value.split(".")
    if not fields or len(set(fields)) != len(fields):
        raise ValueError("invalid compressed tag")
    if any(not TAG.fullmatch(field) for field in fields):
        raise ValueError("invalid compressed tag")
    return fields


def _asset(asset):
    keys = {"filename", "sha256", "size", "yanked"}
    if not isinstance(asset, dict) or set(asset) != keys:
        raise ValueError("invalid asset shape")
    filename = asset["filename"]
    if (
        not isinstance(filename, str)
        or not filename
        or len(filename) > 512
        or "/" in filename
        or "\\" in filename
        or not filename.endswith(".whl")
        or not isinstance(asset["sha256"], str)
        or not SHA256.fullmatch(asset["sha256"])
        or type(asset["size"]) is not int
        or asset["size"] <= 0
        or type(asset["yanked"]) is not bool
    ):
        raise ValueError("invalid asset")
    fields = filename[:-4].split("-")
    if len(fields) == 5:
        distribution, version, python_tag, abi_tag, platform_tag = fields
        build = None
    elif len(fields) == 6:
        distribution, version, build, python_tag, abi_tag, platform_tag = fields
        if not BUILD.fullmatch(build):
            raise ValueError("invalid build tag")
    else:
        raise ValueError("invalid wheel filename")
    if not TAG.fullmatch(distribution) or not VERSION.fullmatch(version):
        raise ValueError("invalid wheel identity")
    python_tags = _components(python_tag)
    abi_tags = _components(abi_tag)
    platform_tags = _components(platform_tag)
    return distribution, version, build, python_tags, abi_tags, platform_tags


def _build_key(build):
    if build is None:
        return (0, "", 0)
    boundary = 0
    while boundary < len(build) and "0" <= build[boundary] <= "9":
        boundary += 1
    return (int(build[:boundary]), build[boundary:].casefold(), 1)


def _empty(decision):
    return {
        "decision": decision,
        "filename": None,
        "sha256": None,
        "size": None,
        "matched_tag": None,
        "build": None,
    }


def select_wheel(target, assets):
    ranking = _target(target)
    if not isinstance(assets, list) or len(assets) > 10000:
        raise ValueError("invalid asset inventory")
    candidates = []
    expected_distribution = target["project"].replace("-", "_")
    for asset in assets:
        distribution, version, build, python_tags, abi_tags, platform_tags = _asset(
            asset
        )
        if (
            distribution.casefold() != expected_distribution
            or version != target["version"]
            or (asset["yanked"] and not target["allow_yanked"])
        ):
            continue
        rank = None
        matched = None
        for python_tag in python_tags:
            for abi_tag in abi_tags:
                for platform_tag in platform_tags:
                    value = f"{python_tag}-{abi_tag}-{platform_tag}"
                    if value in ranking and (rank is None or ranking[value] < rank):
                        rank = ranking[value]
                        matched = value
        if rank is not None:
            candidates.append((rank, _build_key(build), matched, build, asset))
    if not candidates:
        return _empty("no_compatible")
    best_rank = min(candidate[0] for candidate in candidates)
    ranked = [candidate for candidate in candidates if candidate[0] == best_rank]
    best_build = max(candidate[1] for candidate in ranked)
    winners = [candidate for candidate in ranked if candidate[1] == best_build]
    if len(winners) != 1:
        return {
            "decision": "manual_review",
            "candidates": sorted(candidate[4]["filename"] for candidate in winners),
            "matched_tag": target["supported_tags"][best_rank],
            "build": winners[0][3],
        }
    _, _, matched, build, asset = winners[0]
    return {
        "decision": "select",
        "filename": asset["filename"],
        "sha256": asset["sha256"],
        "size": asset["size"],
        "matched_tag": matched,
        "build": build,
    }
