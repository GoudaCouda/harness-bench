#!/usr/bin/env python3
"""Build the deterministic synthetic PPTX inputs for case_06."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parent / "tools"
sys.path.insert(0, TOOLS.as_posix())
from pptx_core import FIXED_ZIP_TIME, canonical_json, sha256_file  # noqa: E402


CASE_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = CASE_ROOT / "fixtures"

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


STYLE_MAP = {
    "schema_version": "case06_presentation_style_v1",
    "canvas": {"cx": 12192000, "cy": 6858000, "ratio": "16:9"},
    "background_color": "F7F9FC",
    "footer_text_format": "纳米 Work｜内部演示｜{slide:02d}",
    "batch_files": {
        "market_brief.pptx": "market_brief.pptx",
        "project_update.pptx": "project_update.pptx",
        "service_review.pptx": "service_review.pptx",
    },
    "input_sha256": {},
    "roles": {
        "TITLE": {
            "geometry": {"x": 720000, "y": 430000, "cx": 10500000, "cy": 900000},
            "font_family": "Noto Sans SC",
            "font_size_pt": 28,
            "font_color": "17365D",
            "bold": True,
            "alignment": "l",
            "vertical_anchor": "ctr",
        },
        "BODY": {
            "geometry": {"x": 720000, "y": 1650000, "cx": 10500000, "cy": 3900000},
            "font_family": "Noto Sans SC",
            "font_size_pt": 18,
            "font_color": "333333",
            "bold": False,
            "alignment": "l",
            "vertical_anchor": "t",
        },
        "ACCENT": {
            "geometry": {"x": 0, "y": 0, "cx": 180000, "cy": 6858000},
            "fill_color": "2F6BFF",
        },
        "FOOTER": {
            "geometry": {"x": 720000, "y": 6220000, "cx": 10500000, "cy": 300000},
            "font_family": "Noto Sans SC",
            "font_size_pt": 9,
            "font_color": "6B7280",
            "bold": False,
            "alignment": "r",
            "vertical_anchor": "ctr",
        },
    },
}

DECKS = {
    "market_brief.pptx": {
        "size": (9144000, 6858000),
        "variant": 0,
        "slides": [
            ("消费观察：用户更重视可直接交付", ["访谈样本显示，用户希望减少格式返工。", "本页仅陈述合成研究结论，不代表真实业务数据。"]),
            ("三类高频交付", ["报告：要求结构清楚、引用完整。", "演示：要求版式统一、可直接汇报。", "表格：要求公式可复核、字段可追溯。"]),
            ("下一步：用小范围验证校准", ["先验证任务完成率，再决定是否扩大投入。", "所有示例、数字和结论均为合成素材。"]),
        ],
    },
    "project_update.pptx": {
        "size": (12192000, 6858000),
        "variant": 1,
        "slides": [
            ("项目进展：环境构建进入验证阶段", ["已完成任务规范、输入资产和自动验收设计。", "当前材料为合成项目，不对应真实内部项目。"]),
            ("本周完成事项", ["完成固定初态。", "补齐最小错误反例。", "增加副作用保护检查。"]),
            ("下周交付", ["运行教师模型小范围验证。", "记录首次成功率、失败原因和资源消耗。"]),
        ],
    },
    "service_review.pptx": {
        "size": (10058400, 5669280),
        "variant": 2,
        "slides": [
            ("服务复盘：交付质量比回复速度更重要", ["用户需要能打开、能编辑、能复核的最终文件。", "该判断来自合成任务设定。"]),
            ("发现的三个问题", ["格式不一致增加人工返工。", "文件命名不统一影响查找。", "缺少验收导致错误进入交付。"]),
            ("改进动作", ["统一演示模板。", "保留原始文案和页序。", "交付前自动检查文件结构。"]),
        ],
    },
}


def _run(text: str, font: str, size: int, color: str, bold: bool) -> str:
    return (
        f'<a:r><a:rPr lang="zh-CN" sz="{size * 100}" b="{1 if bold else 0}">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="{escape(font)}"/><a:ea typeface="{escape(font)}"/>'
        f'<a:cs typeface="{escape(font)}"/></a:rPr><a:t>{escape(text)}</a:t></a:r>'
    )


def _text_shape(
    shape_id: int,
    name: str,
    paragraphs: list[str],
    geometry: tuple[int, int, int, int],
    font: str,
    size: int,
    color: str,
    bold: bool,
    align: str,
    fill: str | None = None,
) -> str:
    x, y, cx, cy = geometry
    fill_xml = (
        f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
    )
    body = "".join(
        f'<a:p><a:pPr algn="{align}"/>{_run(text, font, size, color, bold)}'
        f'<a:endParaRPr lang="zh-CN" sz="{size * 100}"/></a:p>'
        for text in paragraphs
    )
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{escape(name)}"/>'
        '<p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>{fill_xml}</p:spPr>'
        f'<p:txBody><a:bodyPr anchor="t"/><a:lstStyle/>{body}</p:txBody></p:sp>'
    )


def _accent_shape(shape_id: int, name: str, geometry: tuple[int, int, int, int], fill: str) -> str:
    x, y, cx, cy = geometry
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{escape(name)}"/>'
        '<p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></p:spPr></p:sp>'
    )


def _slide_xml(title: str, body: list[str], index: int, variant: int, standard: bool) -> str:
    if standard:
        roles = STYLE_MAP["roles"]
        title_spec = roles["TITLE"]
        body_spec = roles["BODY"]
        footer_spec = roles["FOOTER"]
        accent_spec = roles["ACCENT"]
        title_geometry = tuple(title_spec["geometry"][key] for key in ("x", "y", "cx", "cy"))
        body_geometry = tuple(body_spec["geometry"][key] for key in ("x", "y", "cx", "cy"))
        footer_geometry = tuple(footer_spec["geometry"][key] for key in ("x", "y", "cx", "cy"))
        accent_geometry = tuple(accent_spec["geometry"][key] for key in ("x", "y", "cx", "cy"))
        title_style = (title_spec["font_family"], title_spec["font_size_pt"], title_spec["font_color"], title_spec["bold"], title_spec["alignment"])
        body_style = (body_spec["font_family"], body_spec["font_size_pt"], body_spec["font_color"], body_spec["bold"], body_spec["alignment"])
        footer_style = (footer_spec["font_family"], footer_spec["font_size_pt"], footer_spec["font_color"], footer_spec["bold"], footer_spec["alignment"])
        accent_color = accent_spec["fill_color"]
        footer_text = STYLE_MAP["footer_text_format"].format(slide=index)
        background = STYLE_MAP["background_color"]
    else:
        fonts = ["Arial", "Calibri", "Microsoft YaHei"]
        colors = ["9C2A2A", "20603D", "7030A0"]
        title_geometry = (380000 + variant * 90000, 250000 + variant * 80000, 7900000, 1100000)
        body_geometry = (650000, 1550000 + variant * 120000, 7600000 + variant * 500000, 3600000)
        footer_geometry = (500000, 6100000, 7600000, 350000)
        accent_geometry = (0, 0, 260000 + variant * 80000, 6858000)
        title_style = (fonts[variant], 24 + variant * 2, colors[variant], variant != 1, ["ctr", "l", "r"][variant])
        body_style = (fonts[(variant + 1) % 3], 14 + variant * 2, ["555555", "1F4E78", "7F6000"][variant], False, ["l", "ctr", "l"][variant])
        footer_style = (fonts[variant], 8 + variant, "888888", False, "l")
        accent_color = ["D95F59", "70AD47", "C55A11"][variant]
        footer_text = f"原始页脚-{variant + 1}-{index}"
        background = ["FFFFFF", "FFF8EE", "F2F2F2"][variant]
    shapes = [
        _accent_shape(2, f"ACCENT__s{index}", accent_geometry, accent_color),
        _text_shape(3, f"TITLE__s{index}", [title], title_geometry, *title_style),
        _text_shape(4, f"BODY__s{index}", body, body_geometry, *body_style),
        _text_shape(5, f"FOOTER__s{index}", [footer_text], footer_geometry, *footer_style),
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:sld xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">'
        f'<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="{background}"/></a:solidFill>'
        '<a:effectLst/></p:bgPr></p:bg><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        + "".join(shapes)
        + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
    )


def _package(slides: list[tuple[str, list[str]]], size: tuple[int, int], variant: int, standard: bool) -> dict[str, bytes]:
    slide_overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, len(slides) + 1)
    )
    members: dict[str, bytes] = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
            '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
            '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
            '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
            '<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>'
            '<Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>'
            '<Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            + slide_overrides
            + '</Types>'
        ).encode(),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{REL_NS}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '</Relationships>'
        ).encode(),
        "docProps/core.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>case_06 synthetic deck</dc:title><dc:creator>agent_sft</dc:creator>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">2026-07-20T00:00:00Z</dcterms:created>'
            '<dcterms:modified xsi:type="dcterms:W3CDTF">2026-07-20T00:00:00Z</dcterms:modified>'
            '</cp:coreProperties>'
        ).encode(),
        "docProps/app.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            f'<Application>agent_sft</Application><Slides>{len(slides)}</Slides></Properties>'
        ).encode(),
        "ppt/presProps.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentationPr xmlns:p="{P_NS}"/>'.encode(),
        "ppt/viewProps.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:viewPr xmlns:p="{P_NS}"/>'.encode(),
        "ppt/tableStyles.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:tblStyleLst xmlns:a="{A_NS}" def="{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}"/>'.encode(),
        "ppt/theme/theme1.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="{A_NS}" name="Synthetic">'
            '<a:themeElements><a:clrScheme name="Synthetic"><a:dk1><a:srgbClr val="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
            '<a:dk2><a:srgbClr val="17365D"/></a:dk2><a:lt2><a:srgbClr val="F7F9FC"/></a:lt2>'
            '<a:accent1><a:srgbClr val="2F6BFF"/></a:accent1><a:accent2><a:srgbClr val="70AD47"/></a:accent2>'
            '<a:accent3><a:srgbClr val="C55A11"/></a:accent3><a:accent4><a:srgbClr val="7030A0"/></a:accent4>'
            '<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5><a:accent6><a:srgbClr val="ED7D31"/></a:accent6>'
            '<a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>'
            '<a:fontScheme name="Synthetic"><a:majorFont><a:latin typeface="Noto Sans SC"/><a:ea typeface="Noto Sans SC"/><a:cs typeface="Noto Sans SC"/></a:majorFont>'
            '<a:minorFont><a:latin typeface="Noto Sans SC"/><a:ea typeface="Noto Sans SC"/><a:cs typeface="Noto Sans SC"/></a:minorFont></a:fontScheme>'
            '<a:fmtScheme name="Synthetic"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
            '<a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
            '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
            '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>'
            '</a:themeElements></a:theme>'
        ).encode(),
        "ppt/slideMasters/slideMaster1.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">'
            '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            '</p:spTree></p:cSld><p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>'
            '<p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles/></p:sldMaster>'
        ).encode(),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL_NS}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
            '</Relationships>'
        ).encode(),
        "ppt/slideLayouts/slideLayout1.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}" type="blank">'
            '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
        ).encode(),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL_NS}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
            '</Relationships>'
        ).encode(),
    }
    slide_ids = []
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>',
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>',
        '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>',
    ]
    for i, (title, body) in enumerate(slides, 1):
        rel_id = i + 4
        slide_ids.append(f'<p:sldId id="{255 + i}" r:id="rId{rel_id}"/>')
        rels.append(f'<Relationship Id="rId{rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>')
        members[f"ppt/slides/slide{i}.xml"] = _slide_xml(title, body, i, variant, standard).encode()
        members[f"ppt/slides/_rels/slide{i}.xml.rels"] = (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL_NS}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            '</Relationships>'
        ).encode()
    if standard:
        cx, cy = STYLE_MAP["canvas"]["cx"], STYLE_MAP["canvas"]["cy"]
    else:
        cx, cy = size
    members["ppt/presentation.xml"] = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">'
        f'<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>{"".join(slide_ids)}</p:sldIdLst>'
        f'<p:sldSz cx="{cx}" cy="{cy}" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    ).encode()
    members["ppt/_rels/presentation.xml.rels"] = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL_NS}">{"".join(rels)}</Relationships>'
    ).encode()
    return members


def _write_pptx(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name])


def main() -> int:
    decks_dir = FIXTURES / "decks"
    decks_dir.mkdir(parents=True, exist_ok=True)
    for name, descriptor in DECKS.items():
        _write_pptx(
            decks_dir / name,
            _package(descriptor["slides"], descriptor["size"], descriptor["variant"], False),
        )
    STYLE_MAP["input_sha256"] = {
        name: sha256_file(decks_dir / name) for name in sorted(DECKS)
    }
    (FIXTURES / "style_map.json").write_text(
        json.dumps(STYLE_MAP, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    template_slides = [("标准标题示例", ["正文第一条。", "正文第二条。"])]
    _write_pptx(
        FIXTURES / "brand_template.pptx",
        _package(template_slides, (12192000, 6858000), 0, True),
    )
    manifest = {
        "schema_version": "case06_fixture_manifest_v1",
        "generated_at": "2026-07-20T00:00:00Z",
        "source": "fully_synthetic",
        "license": "CC0-1.0",
        "files": [],
    }
    for path in sorted(FIXTURES.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            manifest["files"].append(
                {
                    "path": path.relative_to(CASE_ROOT).as_posix(),
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                    "source": "synthetic_case06_builder",
                }
            )
    (FIXTURES / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(hashlib.sha256(canonical_json(manifest)).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
