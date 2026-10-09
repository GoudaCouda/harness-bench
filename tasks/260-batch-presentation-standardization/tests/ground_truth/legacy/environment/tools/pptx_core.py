#!/usr/bin/env python3
"""Pure-stdlib PPTX inspection and deterministic style transformation helpers.

This module is candidate-visible.  It deliberately contains no verifier rule or
reference answer: every transformation parameter comes from the visible style
map in the reset workspace.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)

FORBIDDEN_MEMBER_MARKERS = (
    "vbaproject",
    "activex",
    "embeddings/",
    "customxml/",
    "externallinks/",
    "xmlsignatures/",
)
MAX_MEMBER_COUNT = 256
MAX_UNCOMPRESSED_BYTES = 8 * 1024 * 1024
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


class PptxContractError(ValueError):
    """A stable, payload-free candidate-tool failure."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _safe_member_name(name: str) -> bool:
    pure = PurePosixPath(name)
    return (
        bool(name)
        and not pure.is_absolute()
        and ".." not in pure.parts
        and "\\" not in name
        and "\x00" not in name
    )


def read_package(path: Path) -> dict[str, bytes]:
    if path.is_symlink() or not path.is_file():
        raise PptxContractError("input_not_regular")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise PptxContractError("duplicate_package_member")
            if len(names) > MAX_MEMBER_COUNT:
                raise PptxContractError("package_member_limit")
            if any(not _safe_member_name(name) for name in names):
                raise PptxContractError("unsafe_package_member")
            lowered = [name.lower() for name in names]
            if any(
                marker in name
                for name in lowered
                for marker in FORBIDDEN_MEMBER_MARKERS
            ):
                raise PptxContractError("active_content_forbidden")
            total = sum(info.file_size for info in infos)
            if total > MAX_UNCOMPRESSED_BYTES:
                raise PptxContractError("package_size_limit")
            payload = {name: archive.read(name) for name in names}
    except (zipfile.BadZipFile, OSError) as exc:
        raise PptxContractError("invalid_pptx_package") from exc
    required = {
        "[Content_Types].xml",
        "_rels/.rels",
        "ppt/presentation.xml",
        "ppt/_rels/presentation.xml.rels",
    }
    if not required.issubset(payload):
        raise PptxContractError("required_package_member_missing")
    return payload


def parse_xml(blob: bytes) -> ET.Element:
    upper = blob[:2048].upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise PptxContractError("xml_declaration_forbidden")
    try:
        return ET.fromstring(blob)
    except ET.ParseError as exc:
        raise PptxContractError("invalid_package_xml") from exc


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_package(path: Path, members: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".next")
    if staging.exists() or staging.is_symlink():
        raise PptxContractError("staging_path_exists")
    try:
        with zipfile.ZipFile(staging, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(members):
                info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, members[name])
        os.replace(staging, path)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise


def _slide_names(members: dict[str, bytes]) -> list[str]:
    root = parse_xml(members["ppt/presentation.xml"])
    rels = parse_xml(members["ppt/_rels/presentation.xml.rels"])
    targets: dict[str, str] = {}
    for rel in rels:
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if rel.attrib.get("TargetMode") == "External":
            raise PptxContractError("external_relationship_forbidden")
        if rel_id:
            targets[rel_id] = target
    names: list[str] = []
    for item in root.findall(".//p:sldIdLst/p:sldId", NS):
        rel_id = item.attrib.get(f"{{{NS['r']}}}id")
        target = targets.get(rel_id or "")
        if not target or not target.startswith("slides/"):
            raise PptxContractError("slide_relationship_invalid")
        names.append("ppt/" + target)
    if not names or any(name not in members for name in names):
        raise PptxContractError("slide_member_missing")
    return names


def _shape_role(shape: ET.Element) -> tuple[str, str, str]:
    node = shape.find("p:nvSpPr/p:cNvPr", NS)
    if node is None:
        raise PptxContractError("shape_identity_missing")
    name = node.attrib.get("name", "")
    role = name.split("__", 1)[0]
    if role not in {"TITLE", "BODY", "ACCENT", "FOOTER"}:
        raise PptxContractError("shape_role_invalid")
    return role, node.attrib.get("id", ""), name


def _shape_geometry(shape: ET.Element) -> dict[str, int]:
    xfrm = shape.find("p:spPr/a:xfrm", NS)
    if xfrm is None:
        raise PptxContractError("shape_geometry_missing")
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        raise PptxContractError("shape_geometry_missing")
    try:
        return {
            "x": int(off.attrib["x"]),
            "y": int(off.attrib["y"]),
            "cx": int(ext.attrib["cx"]),
            "cy": int(ext.attrib["cy"]),
        }
    except (KeyError, ValueError) as exc:
        raise PptxContractError("shape_geometry_invalid") from exc


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(".//a:t", NS))


def inspect_pptx(path: Path) -> dict[str, object]:
    members = read_package(path)
    presentation = parse_xml(members["ppt/presentation.xml"])
    size = presentation.find("p:sldSz", NS)
    if size is None:
        raise PptxContractError("slide_size_missing")
    slides: list[dict[str, object]] = []
    for index, name in enumerate(_slide_names(members), 1):
        root = parse_xml(members[name])
        shapes: list[dict[str, object]] = []
        for shape in root.findall(".//p:spTree/p:sp", NS):
            role, shape_id, shape_name = _shape_role(shape)
            paragraphs = [
                _paragraph_text(paragraph)
                for paragraph in shape.findall("p:txBody/a:p", NS)
            ]
            shapes.append(
                {
                    "role": role,
                    "id": shape_id,
                    "name": shape_name,
                    "geometry": _shape_geometry(shape),
                    "paragraphs": paragraphs,
                }
            )
        slides.append({"index": index, "member": name, "shapes": shapes})
    return {
        "sha256": sha256_file(path),
        "slide_size": {"cx": int(size.attrib["cx"]), "cy": int(size.attrib["cy"])},
        "slide_count": len(slides),
        "slides": slides,
    }


def _set_solid_fill(parent: ET.Element, color: str) -> None:
    for child in list(parent):
        if child.tag in {
            f"{{{NS['a']}}}solidFill",
            f"{{{NS['a']}}}noFill",
            f"{{{NS['a']}}}gradFill",
            f"{{{NS['a']}}}pattFill",
            f"{{{NS['a']}}}blipFill",
        }:
            parent.remove(child)
    fill = ET.SubElement(parent, f"{{{NS['a']}}}solidFill")
    ET.SubElement(fill, f"{{{NS['a']}}}srgbClr", {"val": color})


def _set_no_fill(parent: ET.Element) -> None:
    for child in list(parent):
        if child.tag in {
            f"{{{NS['a']}}}solidFill",
            f"{{{NS['a']}}}noFill",
            f"{{{NS['a']}}}gradFill",
            f"{{{NS['a']}}}pattFill",
            f"{{{NS['a']}}}blipFill",
        }:
            parent.remove(child)
    ET.SubElement(parent, f"{{{NS['a']}}}noFill")


def _set_text_style(shape: ET.Element, role_spec: dict[str, object]) -> None:
    tx_body = shape.find("p:txBody", NS)
    if tx_body is None:
        raise PptxContractError("text_body_missing")
    body_pr = tx_body.find("a:bodyPr", NS)
    if body_pr is None:
        raise PptxContractError("body_properties_missing")
    body_pr.attrib["anchor"] = str(role_spec["vertical_anchor"])
    for paragraph in tx_body.findall("a:p", NS):
        paragraph_properties = paragraph.find("a:pPr", NS)
        if paragraph_properties is None:
            paragraph_properties = ET.Element(f"{{{NS['a']}}}pPr")
            paragraph.insert(0, paragraph_properties)
        paragraph_properties.attrib["algn"] = str(role_spec["alignment"])
        text_properties = list(paragraph.findall("a:r/a:rPr", NS))
        end_properties = paragraph.find("a:endParaRPr", NS)
        if end_properties is not None:
            text_properties.append(end_properties)
        if not text_properties:
            raise PptxContractError("text_run_properties_missing")
        for properties in text_properties:
            properties.attrib["lang"] = "zh-CN"
            properties.attrib["sz"] = str(int(role_spec["font_size_pt"]) * 100)
            properties.attrib["b"] = "1" if role_spec["bold"] else "0"
            _set_solid_fill(properties, str(role_spec["font_color"]))
            for tag in ("latin", "ea", "cs"):
                node = properties.find(f"a:{tag}", NS)
                if node is None:
                    node = ET.SubElement(properties, f"{{{NS['a']}}}{tag}")
                node.attrib["typeface"] = str(role_spec["font_family"])


def _set_shape_geometry(shape: ET.Element, geometry: dict[str, object]) -> None:
    xfrm = shape.find("p:spPr/a:xfrm", NS)
    if xfrm is None:
        raise PptxContractError("shape_geometry_missing")
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        raise PptxContractError("shape_geometry_missing")
    off.attrib.update({"x": str(geometry["x"]), "y": str(geometry["y"])})
    ext.attrib.update({"cx": str(geometry["cx"]), "cy": str(geometry["cy"])})


def _set_footer_text(shape: ET.Element, value: str) -> None:
    text_nodes = shape.findall("p:txBody/a:p/a:r/a:t", NS)
    if len(text_nodes) != 1:
        raise PptxContractError("footer_structure_invalid")
    text_nodes[0].text = value


def standardize_pptx(
    source: Path,
    destination: Path,
    style_map: dict[str, object],
) -> None:
    members = read_package(source)
    presentation = parse_xml(members["ppt/presentation.xml"])
    size = presentation.find("p:sldSz", NS)
    if size is None:
        raise PptxContractError("slide_size_missing")
    canvas = style_map["canvas"]
    assert isinstance(canvas, dict)
    size.attrib.update({"cx": str(canvas["cx"]), "cy": str(canvas["cy"])})
    members["ppt/presentation.xml"] = xml_bytes(presentation)

    role_specs = style_map["roles"]
    assert isinstance(role_specs, dict)
    footer_format = str(style_map["footer_text_format"])
    for slide_index, name in enumerate(_slide_names(members), 1):
        root = parse_xml(members[name])
        shape_by_role: dict[str, ET.Element] = {}
        for shape in root.findall(".//p:spTree/p:sp", NS):
            role, _, _ = _shape_role(shape)
            if role in shape_by_role:
                raise PptxContractError("duplicate_shape_role")
            shape_by_role[role] = shape
        if set(shape_by_role) != {"TITLE", "BODY", "ACCENT", "FOOTER"}:
            raise PptxContractError("required_shape_role_missing")
        for role, shape in shape_by_role.items():
            role_spec = role_specs[role]
            assert isinstance(role_spec, dict)
            _set_shape_geometry(shape, role_spec["geometry"])
            shape_properties = shape.find("p:spPr", NS)
            if shape_properties is None:
                raise PptxContractError("shape_properties_missing")
            if role == "ACCENT":
                _set_solid_fill(shape_properties, str(role_spec["fill_color"]))
            else:
                _set_no_fill(shape_properties)
                if role == "FOOTER":
                    _set_footer_text(shape, footer_format.format(slide=slide_index))
                _set_text_style(shape, role_spec)
        common_slide_data = root.find("p:cSld", NS)
        if common_slide_data is None:
            raise PptxContractError("common_slide_data_missing")
        background = common_slide_data.find("p:bg", NS)
        if background is not None:
            common_slide_data.remove(background)
        background = ET.Element(f"{{{NS['p']}}}bg")
        background_properties = ET.SubElement(background, f"{{{NS['p']}}}bgPr")
        _set_solid_fill(background_properties, str(style_map["background_color"]))
        ET.SubElement(background_properties, f"{{{NS['a']}}}effectLst")
        common_slide_data.insert(0, background)
        members[name] = xml_bytes(root)
    write_package(destination, members)


def resolve_inside(root: Path, relative: str) -> Path:
    if not relative or "\x00" in relative:
        raise PptxContractError("path_invalid")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        raise PptxContractError("path_outside_workspace")
    candidate = root.joinpath(*pure.parts)
    resolved_root = root.resolve()
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise PptxContractError("path_outside_workspace") from exc
    return candidate


def assert_regular_tree(path: Path) -> None:
    if path.is_symlink():
        raise PptxContractError("symlink_forbidden")
    mode = path.lstat().st_mode
    if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        raise PptxContractError("special_file_forbidden")
