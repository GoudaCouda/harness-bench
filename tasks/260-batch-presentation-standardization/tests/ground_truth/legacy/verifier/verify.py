#!/usr/bin/env python3
"""Independent deterministic verifier for case_06.

The verifier parses Open Packaging Convention and PresentationML directly.  It
does not import or execute any candidate-visible tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET


CASE_ROOT = Path(__file__).resolve().parents[1]
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
FORBIDDEN = ("vbaproject", "activex", "embeddings/", "customxml/", "externallinks/", "xmlsignatures/")
MAX_MEMBERS = 256
MAX_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024


class CandidateError(ValueError):
    pass


class InternalError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def parse_xml(blob: bytes) -> ET.Element:
    upper = blob.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise CandidateError("xml_declaration_forbidden")
    try:
        return ET.fromstring(blob)
    except ET.ParseError as exc:
        raise CandidateError("xml_invalid") from exc


def read_pptx(path: Path) -> dict[str, bytes]:
    if path.is_symlink() or not path.is_file():
        raise CandidateError("output_not_regular")
    try:
        archive_size = path.stat().st_size
    except OSError as exc:
        raise CandidateError("output_stat_failed") from exc
    if not 1 <= archive_size <= MAX_ARCHIVE_BYTES:
        raise CandidateError("archive_size_limit")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise CandidateError("duplicate_member")
            if len(names) > MAX_MEMBERS or sum(info.file_size for info in infos) > MAX_BYTES:
                raise CandidateError("package_limit")
            for info in infos:
                name = info.filename
                pure = PurePosixPath(name)
                if not name or pure.is_absolute() or ".." in pure.parts or "\\" in name or "\x00" in name:
                    raise CandidateError("unsafe_member")
                if any(marker in name.lower() for marker in FORBIDDEN):
                    raise CandidateError("active_content")
                mode = info.external_attr >> 16
                if (
                    info.create_system != 3
                    or stat.S_IFMT(mode) != stat.S_IFREG
                    or stat.S_IMODE(mode) != 0o644
                    or info.is_dir()
                    or info.flag_bits & 0x1
                    or info.compress_type != zipfile.ZIP_DEFLATED
                    or info.file_size > MAX_BYTES
                    or info.compress_size > MAX_ARCHIVE_BYTES
                ):
                    raise CandidateError("unsafe_member_type_or_encoding")
            members = {name: archive.read(name) for name in names}
    except (
        OSError,
        EOFError,
        NotImplementedError,
        RuntimeError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        raise CandidateError("invalid_package") from exc
    required = {"[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"}
    if not required.issubset(members):
        raise CandidateError("package_part_missing")
    for name, payload in members.items():
        if name.endswith(".rels"):
            root = parse_xml(payload)
            if any(rel.attrib.get("TargetMode") == "External" for rel in root):
                raise CandidateError("external_relationship")
    return members


def slide_names(members: dict[str, bytes]) -> list[str]:
    presentation = parse_xml(members["ppt/presentation.xml"])
    relationships = parse_xml(members["ppt/_rels/presentation.xml.rels"])
    targets = {rel.attrib.get("Id"): rel.attrib.get("Target") for rel in relationships}
    result: list[str] = []
    for slide in presentation.findall(".//p:sldIdLst/p:sldId", NS):
        rel_id = slide.attrib.get(f"{{{NS['r']}}}id")
        target = targets.get(rel_id)
        if not isinstance(target, str) or not target.startswith("slides/"):
            raise CandidateError("slide_relationship")
        name = "ppt/" + target
        if name not in members:
            raise CandidateError("slide_missing")
        result.append(name)
    if not result:
        raise CandidateError("slides_empty")
    return result


def presentation_size(members: dict[str, bytes]) -> dict[str, int]:
    root = parse_xml(members["ppt/presentation.xml"])
    node = root.find("p:sldSz", NS)
    if node is None:
        raise CandidateError("slide_size_missing")
    try:
        return {"cx": int(node.attrib["cx"]), "cy": int(node.attrib["cy"])}
    except (KeyError, ValueError) as exc:
        raise CandidateError("slide_size_invalid") from exc


def direct_color(parent: ET.Element) -> str | None:
    node = parent.find("a:solidFill/a:srgbClr", NS)
    return node.attrib.get("val") if node is not None else None


def geometry(shape: ET.Element) -> dict[str, int]:
    xfrm = shape.find("p:spPr/a:xfrm", NS)
    if xfrm is None:
        raise CandidateError("geometry_missing")
    off, ext = xfrm.find("a:off", NS), xfrm.find("a:ext", NS)
    if off is None or ext is None:
        raise CandidateError("geometry_missing")
    try:
        return {"x": int(off.attrib["x"]), "y": int(off.attrib["y"]), "cx": int(ext.attrib["cx"]), "cy": int(ext.attrib["cy"])}
    except (KeyError, ValueError) as exc:
        raise CandidateError("geometry_invalid") from exc


def text_properties(node: ET.Element) -> dict[str, Any]:
    fonts = {}
    for tag in ("latin", "ea", "cs"):
        child = node.find(f"a:{tag}", NS)
        fonts[tag] = child.attrib.get("typeface") if child is not None else None
    try:
        size = int(node.attrib.get("sz", "-1"))
    except ValueError as exc:
        raise CandidateError("text_size_invalid") from exc
    return {
        "fonts": fonts,
        "size": size,
        "bold": node.attrib.get("b"),
        "color": direct_color(node),
    }


def slide_snapshot(blob: bytes) -> dict[str, Any]:
    root = parse_xml(blob)
    background = root.find("p:cSld/p:bg/p:bgPr", NS)
    result: dict[str, Any] = {"background": direct_color(background) if background is not None else None, "shapes": []}
    seen: set[str] = set()
    for shape in root.findall(".//p:spTree/p:sp", NS):
        identity = shape.find("p:nvSpPr/p:cNvPr", NS)
        if identity is None:
            raise CandidateError("shape_identity_missing")
        name = identity.attrib.get("name", "")
        role = name.split("__", 1)[0]
        if role not in {"TITLE", "BODY", "ACCENT", "FOOTER"} or role in seen:
            raise CandidateError("shape_role_invalid")
        seen.add(role)
        paragraphs = []
        for paragraph in shape.findall("p:txBody/a:p", NS):
            text = "".join(node.text or "" for node in paragraph.findall(".//a:t", NS))
            ppr = paragraph.find("a:pPr", NS)
            props = [text_properties(node) for node in paragraph.findall("a:r/a:rPr", NS)]
            end = paragraph.find("a:endParaRPr", NS)
            if end is not None:
                props.append(text_properties(end))
            paragraphs.append({"text": text, "alignment": ppr.attrib.get("algn") if ppr is not None else None, "properties": props})
        sp_pr = shape.find("p:spPr", NS)
        body_pr = shape.find("p:txBody/a:bodyPr", NS)
        result["shapes"].append(
            {
                "id": identity.attrib.get("id"),
                "name": name,
                "role": role,
                "geometry": geometry(shape),
                "fill": direct_color(sp_pr) if sp_pr is not None else None,
                "no_fill": sp_pr.find("a:noFill", NS) is not None if sp_pr is not None else False,
                "anchor": body_pr.attrib.get("anchor") if body_pr is not None else None,
                "paragraphs": paragraphs,
            }
        )
    if seen != {"TITLE", "BODY", "ACCENT", "FOOTER"}:
        raise CandidateError("shape_role_missing")
    return result


def by_role(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {shape["role"]: shape for shape in snapshot["shapes"]}


def text_signature(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    roles = by_role(snapshot)
    return [
        {
            "role": role,
            "id": roles[role]["id"],
            "name": roles[role]["name"],
            "text": [paragraph["text"] for paragraph in roles[role]["paragraphs"]],
        }
        for role in ("TITLE", "BODY", "ACCENT")
    ]


def role_style_matches(shape: dict[str, Any], role_spec: dict[str, Any]) -> bool:
    if shape["geometry"] != role_spec["geometry"]:
        return False
    if shape["role"] == "ACCENT":
        return shape["fill"] == role_spec["fill_color"]
    if not shape["no_fill"] or shape["anchor"] != role_spec["vertical_anchor"]:
        return False
    expected_properties = {
        "fonts": {"latin": role_spec["font_family"], "ea": role_spec["font_family"], "cs": role_spec["font_family"]},
        "size": int(role_spec["font_size_pt"]) * 100,
        "bold": "1" if role_spec["bold"] else "0",
        "color": role_spec["font_color"],
    }
    for paragraph in shape["paragraphs"]:
        if paragraph["alignment"] != role_spec["alignment"] or not paragraph["properties"]:
            return False
        if any(properties != expected_properties for properties in paragraph["properties"]):
            return False
    return True


@dataclass
class Check:
    check_id: str
    passed: bool
    evidence: dict[str, Any]

    def json(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "evidence": self.evidence}


def workspace_entries(root: Path) -> tuple[set[str], set[str], list[str]]:
    directories: set[str] = set()
    files: set[str] = set()
    unsafe: list[str] = []
    def fail_closed(error: OSError) -> None:
        raise CandidateError("workspace_scan_failed") from error

    for current, dir_names, file_names in os.walk(
        root,
        topdown=True,
        onerror=fail_closed,
        followlinks=False,
    ):
        current_path = Path(current)
        for name in list(dir_names):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                unsafe.append(relative)
                dir_names.remove(name)
            else:
                directories.add(relative)
        for name in file_names:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                unsafe.append(relative)
            else:
                files.add(relative)
    return directories, files, sorted(unsafe)


def verify(workspace: Path) -> tuple[str, list[Check]]:
    style = json.loads((CASE_ROOT / "fixtures/style_map.json").read_text(encoding="utf-8"))
    manifest = json.loads((CASE_ROOT / "environment/workspace_manifest.json").read_text(encoding="utf-8"))
    expected_dirs = set(manifest["directories"])
    protected = {item["path"]: item["sha256"] for item in manifest["protected_files"]}
    outputs = set(manifest["required_outputs"])
    expected_files = set(protected) | outputs
    directories, files, unsafe = workspace_entries(workspace)
    checks = [
        Check(
            "workspace_exact_tree",
            not unsafe and directories == expected_dirs and files == expected_files,
            {
                "unsafe_count": len(unsafe),
                "missing_directory_count": len(expected_dirs - directories),
                "extra_directory_count": len(directories - expected_dirs),
                "missing_file_count": len(expected_files - files),
                "extra_file_count": len(files - expected_files),
            },
        )
    ]
    protected_failures = 0
    for relative, expected_hash in protected.items():
        path = workspace / relative
        if (
            path.is_symlink()
            or not path.is_file()
            or stat.S_IMODE(path.stat().st_mode) != 0o444
            or sha256_file(path) != expected_hash
        ):
            protected_failures += 1
    checks.append(Check("protected_input_integrity", protected_failures == 0, {"failure_count": protected_failures, "checked_count": len(protected)}))

    package_failures = 0
    content_failures = 0
    style_failures = 0
    footer_failures = 0
    layout_failures = 0
    checked_slides = 0
    package_error_types: list[str] = []
    for source_name, output_name in sorted(style["batch_files"].items()):
        input_path = workspace / "inputs/decks" / source_name
        output_path = workspace / "outputs/standardized" / output_name
        try:
            source_members = read_pptx(input_path)
            output_members = read_pptx(output_path)
            source_slide_names = slide_names(source_members)
            output_slide_names = slide_names(output_members)
            if set(source_members) != set(output_members) or source_slide_names != output_slide_names:
                package_failures += 1
                continue
            mutable = {"ppt/presentation.xml", *source_slide_names}
            if any(source_members[name] != output_members[name] for name in source_members if name not in mutable):
                package_failures += 1
            if presentation_size(output_members) != {"cx": style["canvas"]["cx"], "cy": style["canvas"]["cy"]}:
                layout_failures += 1
            for index, slide_name in enumerate(source_slide_names, 1):
                source_snapshot = slide_snapshot(source_members[slide_name])
                output_snapshot = slide_snapshot(output_members[slide_name])
                checked_slides += 1
                if text_signature(source_snapshot) != text_signature(output_snapshot):
                    content_failures += 1
                if output_snapshot["background"] != style["background_color"]:
                    style_failures += 1
                output_roles = by_role(output_snapshot)
                for role in ("TITLE", "BODY", "ACCENT", "FOOTER"):
                    if not role_style_matches(output_roles[role], style["roles"][role]):
                        if output_roles[role]["geometry"] != style["roles"][role]["geometry"]:
                            layout_failures += 1
                        else:
                            style_failures += 1
                footer_text = [item["text"] for item in output_roles["FOOTER"]["paragraphs"]]
                if footer_text != [style["footer_text_format"].format(slide=index)]:
                    footer_failures += 1
        except (
            OSError,
            EOFError,
            NotImplementedError,
            OverflowError,
            RecursionError,
            RuntimeError,
            ValueError,
            CandidateError,
            KeyError,
            TypeError,
        ) as exc:
            package_failures += 1
            package_error_types.append(type(exc).__name__)
    checks.extend(
        [
            Check(
                "pptx_package_integrity",
                package_failures == 0,
                {
                    "failure_count": package_failures,
                    "deck_count": 3,
                    "error_types": sorted(package_error_types),
                },
            ),
            Check("slide_and_content_preservation", content_failures == 0 and checked_slides == 9, {"failure_count": content_failures, "checked_slides": checked_slides}),
            Check("uniform_typography_and_color", style_failures == 0 and checked_slides == 9, {"failure_count": style_failures, "checked_slides": checked_slides}),
            Check("uniform_footer", footer_failures == 0 and checked_slides == 9, {"failure_count": footer_failures, "checked_slides": checked_slides}),
            Check("canvas_alignment_and_geometry", layout_failures == 0 and checked_slides == 9, {"failure_count": layout_failures, "checked_slides": checked_slides}),
        ]
    )
    verdict = "accept" if all(check.passed for check in checks) else "reject"
    return verdict, checks


def write_result(path: Path | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(text, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".next")
    staging.write_text(text, encoding="utf-8")
    os.replace(staging, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    try:
        workspace = args.workspace.resolve(strict=True)
        if not workspace.is_dir() or workspace.is_symlink():
            raise CandidateError("workspace_invalid")
        verdict, checks = verify(workspace)
        score = sum(check.passed for check in checks) / len(checks)
        payload = {"schema_version": "case06_verifier_result_v1", "verdict": verdict, "score": score, "checks": [check.json() for check in checks]}
        write_result(args.result, payload)
        return 0 if verdict == "accept" else 1
    except CandidateError as exc:
        payload = {"schema_version": "case06_verifier_result_v1", "verdict": "reject", "score": 0, "checks": [{"check_id": "workspace_load", "passed": False, "evidence": {"code": str(exc)}}]}
        write_result(args.result, payload)
        return 1
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        payload = {"schema_version": "case06_verifier_result_v1", "verdict": "invalid", "score": 0, "checks": [{"check_id": "verifier_internal", "passed": False, "evidence": {"code": type(exc).__name__}}]}
        write_result(args.result, payload)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
