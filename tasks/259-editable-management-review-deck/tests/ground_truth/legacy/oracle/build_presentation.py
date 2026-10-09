#!/usr/bin/env python3
"""Build a deterministic, fully editable six-slide OOXML presentation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr


SLIDE_W = 12_192_000
SLIDE_H = 6_858_000
FONT = "Noto Sans SC"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def esc(value: object) -> str:
    return escape(str(value), {'"': "&quot;", "'": "&apos;"})


def attr(value: object) -> str:
    return quoteattr(str(value))


def load_metrics(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 11:
        raise ValueError("metrics.csv must contain exactly 11 evidence rows")
    return {(row["metric"], row["scope"]): row for row in rows}


def num(row: dict[str, str], field: str) -> float:
    return float(row[field])


def rgb(value: str) -> str:
    result = value.removeprefix("#").upper()
    if not re.fullmatch(r"[0-9A-F]{6}", result):
        raise ValueError("invalid RGB value")
    return result


def text_run(text: str, size_pt: int, color: str, bold: bool = False) -> str:
    bold_attr = ' b="1"' if bold else ""
    return (
        f'<a:r><a:rPr lang="zh-CN" sz="{size_pt * 100}"{bold_attr} dirty="0">'
        f'<a:solidFill><a:srgbClr val="{rgb(color)}"/></a:solidFill>'
        f'<a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/>'
        f'<a:cs typeface="{FONT}"/></a:rPr><a:t xml:space="preserve">{esc(text)}</a:t></a:r>'
    )


def text_shape(
    shape_id: int,
    name: str,
    descr: str,
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    *,
    size_pt: int = 18,
    color: str = "#101828",
    fill: str | None = None,
    line: str | None = None,
    bold: bool = False,
    align: str = "l",
    valign: str = "ctr",
    margin: int = 100_000,
    radius: bool = False,
) -> str:
    paragraphs = text.split("\n")
    p_xml = "".join(
        f'<a:p><a:pPr algn="{align}"/>{text_run(paragraph, size_pt, color, bold)}'
        f'<a:endParaRPr lang="zh-CN" sz="{size_pt * 100}"/></a:p>'
        for paragraph in paragraphs
    )
    fill_xml = (
        f'<a:solidFill><a:srgbClr val="{rgb(fill)}"/></a:solidFill>'
        if fill
        else "<a:noFill/>"
    )
    line_xml = (
        f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{rgb(line)}"/></a:solidFill></a:ln>'
        if line
        else "<a:ln><a:noFill/></a:ln>"
    )
    geometry = "roundRect" if radius else "rect"
    return (
        '<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{shape_id}" name={attr(name)} descr={attr(descr)}/>'
        '<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
        f'<a:prstGeom prst="{geometry}"><a:avLst/></a:prstGeom>{fill_xml}{line_xml}'
        '</p:spPr><p:txBody>'
        f'<a:bodyPr wrap="square" lIns="{margin}" tIns="{margin}" rIns="{margin}" bIns="{margin}" anchor="{valign}"/>'
        f'<a:lstStyle/>{p_xml}</p:txBody></p:sp>'
    )


def graphic_shape(
    shape_id: int,
    name: str,
    descr: str,
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    fill: str,
    line: str | None = None,
    geometry: str = "rect",
) -> str:
    line_xml = (
        f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{rgb(line)}"/></a:solidFill></a:ln>'
        if line
        else "<a:ln><a:noFill/></a:ln>"
    )
    return (
        '<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{shape_id}" name={attr(name)} descr={attr(descr)}/>'
        '<p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
        f'<a:prstGeom prst="{geometry}"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{rgb(fill)}"/></a:solidFill>{line_xml}'
        '</p:spPr></p:sp>'
    )


class Slide:
    def __init__(self, title: str, background: str, text_color: str) -> None:
        self.title = title
        self.background = background
        self.text_color = text_color
        self.shapes: list[str] = []
        self._id = 2
        self.add_graphic(
            "Background",
            "role:background",
            0,
            0,
            SLIDE_W,
            SLIDE_H,
            fill=background,
        )
        self.add_text(
            "Title",
            "role:title",
            620_000,
            300_000,
            10_950_000,
            720_000,
            title,
            size_pt=28,
            color=text_color,
            bold=True,
            margin=20_000,
        )

    def add_text(self, name: str, descr: str, *args: object, **kwargs: object) -> None:
        self.shapes.append(text_shape(self._id, name, descr, *args, **kwargs))
        self._id += 1

    def add_graphic(self, name: str, descr: str, *args: object, **kwargs: object) -> None:
        self.shapes.append(graphic_shape(self._id, name, descr, *args, **kwargs))
        self._id += 1

    def xml(self) -> str:
        group = (
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
            '</p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/>'
            '<a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/>'
            '</a:xfrm></p:grpSpPr>'
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            f'<p:cSld name={attr(self.title)}><p:spTree>{group}{"".join(self.shapes)}</p:spTree></p:cSld>'
            '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
        )


def add_source(slide: Slide, text: str = "来源：metrics.csv 与 report.md（合成）") -> None:
    slide.add_text(
        "Source",
        "role:source",
        650_000,
        6_390_000,
        10_900_000,
        220_000,
        text,
        size_pt=9,
        color="#667085",
        margin=0,
    )


def build_slides(metrics: dict[tuple[str, str], dict[str, str]], report: str, brand: dict[str, object]) -> list[Slide]:
    required_report_facts = ["21 万元", "0.6 个百分点", "每两周", "不得补造预测值"]
    if any(value not in report for value in required_report_facts):
        raise ValueError("report.md is missing a required evidence statement")
    primary = str(brand["primary_color"])
    accent = str(brand["accent_color"])
    positive = str(brand["positive_color"])
    risk = str(brand["risk_color"])
    background = str(brand["background_color"])
    text_color = str(brand["text_color"])

    total = metrics[("revenue", "total")]
    total_plan = num(total, "plan")
    total_actual = num(total, "actual")
    completion = round(total_actual / total_plan * 100, 1)
    gap = int(total_plan - total_actual)
    gross = metrics[("gross_margin", "total")]
    delivery = metrics[("on_time_delivery", "total")]
    returns = metrics[("return_rate", "total")]
    west_delivery = metrics[("on_time_delivery", "西部")]
    north_return = metrics[("return_rate", "华北")]
    promotion = metrics[("promotion_margin", "total")]
    regions = ["华东", "华南", "华北", "西部"]

    slides: list[Slide] = []
    s1 = Slide(f"第二季度收入完成 {completion:.1f}%，八周内优先修复交付与退货", background, text_color)
    s1.add_text("Subtitle", "role:subtitle", 650_000, 1_120_000, 10_900_000, 460_000, "星桥家居 2026 年第二季度经营复盘｜全部数据为合成材料", size_pt=17, color="#475467", margin=20_000)
    cards = [
        (f"{completion:.1f}%", f"收入完成率\n缺口 {gap} 万元", primary),
        (f"{num(gross, 'actual'):.1f}%", f"综合毛利率\n低于计划 {num(gross, 'plan') - num(gross, 'actual'):.1f} 个百分点", accent),
        (f"{num(delivery, 'actual'):.1f}%", f"按时交付率\n低于目标 {num(delivery, 'plan') - num(delivery, 'actual'):.1f} 个百分点", risk),
    ]
    for index, (value, label, color) in enumerate(cards):
        x = 650_000 + index * 3_720_000
        s1.add_text(f"KPI {index + 1}", f"role:kpi|index={index + 1}", x, 1_850_000, 3_250_000, 1_460_000, f"{value}\n{label}", size_pt=20, color=text_color, fill="#FFFFFF", line=color, bold=True, margin=180_000, radius=True)
    s1.add_text("Focus", "role:conclusion", 650_000, 3_780_000, 10_900_000, 1_500_000, "本次复盘只做三件事\n1）补齐西部交付能力　2）降低华北退货　3）守住促销毛利底线", size_pt=21, color="#FFFFFF", fill=primary, bold=True, margin=240_000, radius=True)
    s1.add_text("Boundary", "role:boundary", 650_000, 5_560_000, 10_900_000, 520_000, "边界：原报告没有八周后的收入预测，本演示不补造预测值。", size_pt=15, color="#475467", fill="#EAECF0", margin=120_000, radius=True)
    add_source(s1)
    slides.append(s1)

    s2 = Slide(f"收入完成 {completion:.1f}%，区域缺口集中在西部和华北", background, text_color)
    s2.add_text("Total", "role:summary", 690_000, 1_070_000, 2_250_000, 820_000, f"计划 {int(total_plan):,} 万元\n实际 {int(total_actual):,} 万元", size_pt=17, color=text_color, fill="#FFFFFF", line=primary, bold=True, margin=100_000, radius=True)
    plot_x = 3_250_000
    max_width = 6_600_000
    scale_max = 360.0
    for i, region in enumerate(regions):
        row = metrics[("revenue", region)]
        plan = num(row, "plan")
        actual = num(row, "actual")
        rate = round(actual / plan * 100, 1)
        gap_value = int(actual - plan)
        y = 1_150_000 + i * 1_080_000
        s2.add_text(f"Region {region}", f"role:category|scope={region}", 720_000, y, 1_450_000, 420_000, region, size_pt=17, color=text_color, bold=True, margin=0)
        s2.add_graphic(f"Plan bar {region}", f"chart_bar|metric=revenue|scope={region}|series=plan|value={int(plan)}|max=360", plot_x, y, round(max_width * plan / scale_max), 190_000, fill="#B2CCFF", geometry="roundRect")
        s2.add_graphic(f"Actual bar {region}", f"chart_bar|metric=revenue|scope={region}|series=actual|value={int(actual)}|max=360", plot_x, y + 250_000, round(max_width * actual / scale_max), 190_000, fill=positive if actual >= plan else risk, geometry="roundRect")
        sign = "+" if gap_value >= 0 else ""
        s2.add_text(f"Region value {region}", f"role:chart_label|scope={region}", 10_050_000, y - 20_000, 1_400_000, 650_000, f"{rate:.1f}%\n{sign}{gap_value} 万元", size_pt=14, color=positive if gap_value >= 0 else risk, bold=True, align="r", margin=0)
    s2.add_text("Legend", "role:legend", 3_250_000, 5_590_000, 5_600_000, 340_000, "浅蓝：计划　绿色：超过计划　红色：低于计划", size_pt=13, color="#475467", margin=0)
    s2.add_text("Gap", "role:evidence", 8_600_000, 5_390_000, 2_950_000, 720_000, "西部缺口 30 万元\n华北缺口 24 万元", size_pt=15, color=risk, fill="#FEF3F2", bold=True, margin=80_000, radius=True)
    add_source(s2, "来源：metrics.csv（合成）；所有条形使用统一比例")
    slides.append(s2)

    s3 = Slide("交付延迟、退货上升和低毛利促销共同拖累结果", background, text_color)
    causes = [
        ("西部交付", f"按时交付率 {num(west_delivery, 'actual'):.1f}%\n影响确认收入 21 万元", risk, "供应链排班缺口"),
        ("华北退货", f"退货率 {num(north_return, 'actual'):.1f}%\n毛利率承压 0.6 个百分点", accent, "包装强度不足"),
        ("促销毛利", f"订单毛利率 {num(promotion, 'actual'):.1f}%\n低于底线 {num(promotion, 'plan') - num(promotion, 'actual'):.1f} 个百分点", primary, "六月促销组合偏低"),
    ]
    for i, (name, value, color, reason) in enumerate(causes):
        x = 670_000 + i * 3_730_000
        s3.add_text(f"Cause {i + 1}", f"role:cause|index={i + 1}", x, 1_250_000, 3_280_000, 1_650_000, f"{name}\n{value}", size_pt=18, color=text_color, fill="#FFFFFF", line=color, bold=True, margin=180_000, radius=True)
        s3.add_graphic(f"Arrow {i + 1}", f"role:flow_arrow|index={i + 1}", x + 1_240_000, 3_130_000, 800_000, 420_000, fill=color, geometry="downArrow")
        s3.add_text(f"Reason {i + 1}", f"role:reason|index={i + 1}", x, 3_750_000, 3_280_000, 900_000, reason, size_pt=17, color="#FFFFFF", fill=color, bold=True, align="ctr", margin=120_000, radius=True)
    s3.add_text("Evidence boundary", "role:boundary", 670_000, 5_080_000, 10_720_000, 820_000, "这些原因均来自报告已给出的事实；华东续约做法可复用，但材料未提供可量化的跨区收入预测。", size_pt=17, color=text_color, fill="#EAECF0", margin=180_000, radius=True)
    add_source(s3)
    slides.append(s3)

    s4 = Slide("先修复最大缺口，再把有效做法复制到其他区域", background, text_color)
    headers = ["优先级", "对象", "八周动作", "责任角色", "验收指标"]
    widths = [900_000, 1_200_000, 4_050_000, 1_650_000, 3_000_000]
    x0, y0 = 650_000, 1_160_000
    x = x0
    for i, (header, width) in enumerate(zip(headers, widths)):
        s4.add_text(f"Header {i + 1}", f"role:table_header|column={i + 1}", x, y0, width, 520_000, header, size_pt=14, color="#FFFFFF", fill=primary, bold=True, align="ctr", margin=70_000)
        x += width
    rows = [
        ("1", "西部", "第 1—2 周补齐中转仓轮班", "供应链", f"按时交付率 ≥ {num(west_delivery, 'plan'):.1f}%"),
        ("2", "华北", "第 1—4 周完成两款新品包装加固", "产品", f"退货率 ≤ {num(north_return, 'plan'):.1f}%"),
        ("3", "促销", "第 3—8 周联合审核促销清单", "销售＋财务", f"订单毛利率 ≥ {num(promotion, 'plan'):.1f}%"),
        ("4", "华东", "提炼重点客户续约动作供跨区复用", "区域销售", "只复用做法，不补造预测"),
    ]
    for r_idx, row in enumerate(rows):
        x = x0
        fill = "#FFFFFF" if r_idx % 2 == 0 else "#F2F4F7"
        for c_idx, (value, width) in enumerate(zip(row, widths)):
            s4.add_text(f"Cell {r_idx + 1}-{c_idx + 1}", f"role:table_cell|row={r_idx + 1}|column={c_idx + 1}", x, y0 + 520_000 + r_idx * 820_000, width, 820_000, value, size_pt=14, color=text_color, fill=fill, line="#D0D5DD", bold=c_idx in {0, 1}, align="ctr" if c_idx in {0, 1, 3} else "l", margin=90_000)
            x += width
    s4.add_text("Priority evidence", "role:evidence", 650_000, 5_200_000, 10_800_000, 730_000, "排序依据：三个负缺口区域中，西部占 41.7%，华北占 33.3%，华南占 25.0%。", size_pt=17, color=text_color, fill="#EAF2FF", line=primary, bold=True, margin=150_000, radius=True)
    add_source(s4)
    slides.append(s4)

    s5 = Slide("八周只跟踪四项指标，每两周复盘一次", background, text_color)
    timeline_x = [1_150_000, 3_500_000, 5_850_000, 8_200_000, 10_550_000]
    labels = ["启动", "第 2 周", "第 4 周", "第 6 周", "第 8 周"]
    s5.add_graphic("Timeline", "role:timeline", 1_150_000, 1_820_000, 9_400_000, 55_000, fill="#98A2B3")
    for i, (x, label) in enumerate(zip(timeline_x, labels)):
        s5.add_graphic(f"Milestone {i + 1}", f"role:milestone|index={i + 1}", x - 130_000, 1_690_000, 260_000, 260_000, fill=primary if i in {0, 4} else "#FFFFFF", line=primary, geometry="ellipse")
        s5.add_text(f"Milestone label {i + 1}", f"role:milestone_label|index={i + 1}", x - 520_000, 2_070_000, 1_040_000, 420_000, label, size_pt=14, color=text_color, bold=True, align="ctr", margin=0)
    metric_cards = [
        ("收入完成率", f"当前 {completion:.1f}%", primary),
        ("按时交付率", f"当前 {num(delivery, 'actual'):.1f}%", risk),
        ("退货率", f"当前 {num(returns, 'actual'):.1f}%", accent),
        ("促销订单毛利率", f"当前 {num(promotion, 'actual'):.1f}%", positive),
    ]
    for i, (name, value, color) in enumerate(metric_cards):
        x = 700_000 + (i % 2) * 5_650_000
        y = 3_020_000 + (i // 2) * 1_160_000
        s5.add_text(f"Tracking {i + 1}", f"role:tracking_metric|index={i + 1}", x, y, 5_100_000, 860_000, f"{name}\n{value}", size_pt=17, color=text_color, fill="#FFFFFF", line=color, bold=True, margin=130_000, radius=True)
    s5.add_text("Cadence", "role:cadence", 700_000, 5_500_000, 10_750_000, 500_000, "复盘节奏：第 2、4、6、8 周各复盘一次；不以预测值替代实际结果。", size_pt=16, color="#FFFFFF", fill=primary, bold=True, align="ctr", margin=100_000, radius=True)
    add_source(s5)
    slides.append(s5)

    s6 = Slide("今天确认责任人与复盘节奏，八周行动即可开始", background, text_color)
    decisions = [
        ("确认四类责任人", "供应链、产品、销售、财务", primary),
        ("确认复盘节奏", "每两周一次，共四次复盘", accent),
        ("确认三项门槛", f"西部交付 ≥ {num(west_delivery, 'plan'):.1f}%｜华北退货 ≤ {num(north_return, 'plan'):.1f}%｜促销毛利 ≥ {num(promotion, 'plan'):.1f}%", positive),
    ]
    for i, (title, detail, color) in enumerate(decisions):
        y = 1_250_000 + i * 1_380_000
        s6.add_graphic(f"Decision number {i + 1}", f"role:decision_number|index={i + 1}", 740_000, y + 110_000, 620_000, 620_000, fill=color, geometry="ellipse")
        s6.add_text(f"Decision index {i + 1}", f"role:decision_index|index={i + 1}", 740_000, y + 110_000, 620_000, 620_000, str(i + 1), size_pt=20, color="#FFFFFF", bold=True, align="ctr", margin=0)
        s6.add_text(f"Decision {i + 1}", f"role:decision|index={i + 1}", 1_650_000, y, 9_700_000, 850_000, f"{title}\n{detail}", size_pt=18, color=text_color, fill="#FFFFFF", line=color, bold=True, margin=140_000, radius=True)
    s6.add_text("Close", "role:conclusion", 740_000, 5_540_000, 10_610_000, 560_000, "确认后按第 1 周计划启动；后续只用实际指标判断进展。", size_pt=18, color="#FFFFFF", fill=primary, bold=True, align="ctr", margin=120_000, radius=True)
    add_source(s6)
    slides.append(s6)
    return slides


def content_types(slide_count: int) -> str:
    slide_overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return (
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
        f'{slide_overrides}</Types>'
    )


def package_parts(slides: list[Slide]) -> dict[str, bytes]:
    count = len(slides)
    sld_ids = "".join(f'<p:sldId id="{255 + i}" r:id="rId{1 + i}"/>' for i in range(1, count + 1))
    pres_rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    pres_rels.extend(f'<Relationship Id="rId{1 + i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>' for i in range(1, count + 1))
    pres_rels.extend([
        f'<Relationship Id="rId{count + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>',
        f'<Relationship Id="rId{count + 3}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>',
        f'<Relationship Id="rId{count + 4}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>',
    ])
    parts: dict[str, str] = {
        "[Content_Types].xml": content_types(count),
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>',
        "docProps/core.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>星桥家居 2026 年第二季度经营复盘</dc:title><dc:creator>case_05 deterministic oracle</dc:creator><cp:lastModifiedBy>case_05 deterministic oracle</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2026-07-01T01:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-07-01T01:00:00Z</dcterms:modified><cp:revision>1</cp:revision></cp:coreProperties>',
        "docProps/app.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>case_05 OOXML builder</Application><PresentationFormat>宽屏</PresentationFormat><Slides>{count}</Slides><Notes>0</Notes><HiddenSlides>0</HiddenSlides><AppVersion>1.0</AppVersion></Properties>',
        "ppt/presentation.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>{sld_ids}</p:sldIdLst><p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/><p:defaultTextStyle><a:defPPr><a:defRPr lang="zh-CN"><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:defRPr></a:defPPr></p:defaultTextStyle></p:presentation>',
        "ppt/_rels/presentation.xml.rels": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(pres_rels)}</Relationships>',
        "ppt/slideMasters/slideMaster1.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle><a:lvl1pPr algn="l"><a:defRPr sz="2800" b="1"><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:defRPr></a:lvl1pPr></p:titleStyle><p:bodyStyle><a:lvl1pPr><a:defRPr sz="1800"><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:defRPr></a:lvl1pPr></p:bodyStyle><p:otherStyle><a:defPPr><a:defRPr lang="zh-CN"><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:defRPr></a:defPPr></p:otherStyle></p:txStyles></p:sldMaster>',
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>',
        "ppt/slideLayouts/slideLayout1.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="空白"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>',
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>',
        "ppt/theme/theme1.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="case_05"><a:themeElements><a:clrScheme name="case_05"><a:dk1><a:srgbClr val="101828"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="344054"/></a:dk2><a:lt2><a:srgbClr val="F8FAFC"/></a:lt2><a:accent1><a:srgbClr val="155EEF"/></a:accent1><a:accent2><a:srgbClr val="F79009"/></a:accent2><a:accent3><a:srgbClr val="039855"/></a:accent3><a:accent4><a:srgbClr val="D92D20"/></a:accent4><a:accent5><a:srgbClr val="667085"/></a:accent5><a:accent6><a:srgbClr val="B2CCFF"/></a:accent6><a:hlink><a:srgbClr val="0000FF"/></a:hlink><a:folHlink><a:srgbClr val="800080"/></a:folHlink></a:clrScheme><a:fontScheme name="case_05"><a:majorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:majorFont><a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:minorFont></a:fontScheme><a:fmtScheme name="case_05"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>',
        "ppt/presProps.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentationPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        "ppt/viewProps.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:viewPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:normalViewPr/><p:slideViewPr/><p:notesTextViewPr/></p:viewPr>',
        "ppt/tableStyles.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>',
    }
    for i, slide in enumerate(slides, 1):
        parts[f"ppt/slides/slide{i}.xml"] = slide.xml()
        parts[f"ppt/slides/_rels/slide{i}.xml.rels"] = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>'
    return {name: value.encode("utf-8") for name, value in parts.items()}


def write_deterministic_zip(path: Path, parts: dict[str, bytes]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            archive.writestr(info, parts[name])
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    report = (workspace / "input" / "report.md").read_text(encoding="utf-8")
    metrics = load_metrics(workspace / "input" / "metrics.csv")
    brand = json.loads((workspace / "input" / "brand.json").read_text(encoding="utf-8"))
    if brand.get("canvas") != "16:9" or brand.get("font_family") != FONT:
        raise ValueError("brand contract does not match the fixed geometry/font")
    slides = build_slides(metrics, report, brand)
    if len(slides) != 6:
        raise ValueError("oracle must build exactly six slides")
    output = workspace / str(brand["required_output"])
    digest = write_deterministic_zip(output, package_parts(slides))
    print(json.dumps({"schema_version": "nami_work_case05_oracle_v1", "output": str(output), "slide_count": len(slides), "sha256": digest}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
