"""Deterministic PNG assets for multimodal-tasks 021-026.

The candidate only receives the PNG. Positions, colors, and printed values that
the task expects the candidate to *see* live in these renders and in the hidden
ground truth; they are deliberately absent from the shipped records.

Rendering goes through matplotlib's Agg backend with its bundled DejaVu fonts, so
the output is byte-stable across machines without any external renderer.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, PathPatch, Polygon  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402
from matplotlib.textpath import TextPath  # noqa: E402

matplotlib.rcParams["lines.scale_dashes"] = False
matplotlib.rcParams["path.simplify"] = False

SANS = "DejaVu Sans"
MONO = "DejaVu Sans Mono"
SERIF = "DejaVu Serif"
SCALE = 2  # output pixels per design pixel

Record = Mapping[str, Any]


def _pt(px: float) -> float:
    """Design pixels -> points (the figure is laid out at 100 design px per inch)."""
    return px * 0.72


def _text_width(value: str, size: float, weight: str = "normal", family: str = SANS) -> float:
    path = TextPath((0, 0), value, size=size, prop=FontProperties(family=family, weight=weight))
    return float(path.get_extents().width)


class Scene:
    def __init__(self, width: int, height: int) -> None:
        self.w, self.h = width, height
        self.fig = plt.figure(figsize=(width / 100, height / 100), dpi=100 * SCALE)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, width)
        self.ax.set_ylim(height, 0)
        self.ax.axis("off")
        self._z = 1.0

    def z(self) -> float:
        self._z += 0.01
        return self._z

    # --- primitives -----------------------------------------------------------------
    def text(
        self,
        x: float,
        y: float,
        value: str,
        *,
        size: float = 12,
        color: str = "#1f2933",
        weight: str = "normal",
        family: str = SANS,
        ha: str = "left",
        alpha: float = 1.0,
    ) -> None:
        self.ax.text(
            x,
            y,
            value,
            fontsize=_pt(size),
            color=color,
            fontweight=weight,
            family=family,
            ha=ha,
            va="baseline",
            alpha=alpha,
            zorder=self.z(),
        )

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fc: str | None = "#ffffff",
        ec: str | None = None,
        lw: float = 1.0,
        r: float = 0.0,
        alpha: float = 1.0,
        dash: tuple[float, float] | None = None,
        shadow: tuple[str, float] | None = None,
    ) -> FancyBboxPatch:
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle=f"round,pad=0,rounding_size={r}" if r else "square,pad=0",
            facecolor=fc if fc else "none",
            edgecolor=ec if ec else "none",
            linewidth=_pt(lw) if ec else 0,
            alpha=alpha,
            zorder=self.z(),
        )
        if dash:
            patch.set_linestyle((0, (_pt(dash[0]), _pt(dash[1]))))
        if shadow:
            patch.set_path_effects(
                [pe.withSimplePatchShadow(offset=(0, -_pt(3)), shadow_rgbFace=shadow[0], alpha=shadow[1])]
            )
        self.ax.add_patch(patch)
        return patch

    def gradient(
        self,
        clip: Any,
        x: float,
        y: float,
        w: float,
        h: float,
        c0: str,
        c1: str,
        *,
        direction: str = "v",
    ) -> None:
        a = np.array(to_rgb(c0))
        b = np.array(to_rgb(c1))
        steps = 256
        ramp = np.linspace(0, 1, steps)[:, None]
        colors = a * (1 - ramp) + b * ramp
        if direction == "v":
            img = colors[:, None, :]
        elif direction == "h":
            img = colors[None, :, :]
        else:  # diagonal
            grid = (np.add.outer(np.linspace(0, 1, steps), np.linspace(0, 1, steps)) / 2)
            img = a * (1 - grid[..., None]) + b * grid[..., None]
        image = self.ax.imshow(
            img,
            extent=(x, x + w, y + h, y),
            aspect="auto",
            interpolation="bilinear",
            zorder=self.z(),
        )
        image.set_clip_path(clip)

    def path(
        self,
        verts: Sequence[tuple[float, float]],
        codes: Sequence[int],
        *,
        fc: str | None = None,
        ec: str | None = None,
        lw: float = 1.0,
        alpha: float = 1.0,
        dash: tuple[float, float] | None = None,
        shadow: tuple[str, float] | None = None,
        cap: str = "round",
    ) -> PathPatch:
        patch = PathPatch(
            MplPath(verts, codes),
            facecolor=fc if fc else "none",
            edgecolor=ec if ec else "none",
            linewidth=_pt(lw) if ec else 0,
            alpha=alpha,
            capstyle=cap,
            joinstyle="round",
            zorder=self.z(),
        )
        if dash:
            patch.set_linestyle((0, (_pt(dash[0]), _pt(dash[1]))))
        if shadow:
            patch.set_path_effects(
                [pe.withSimplePatchShadow(offset=(0, -_pt(3)), shadow_rgbFace=shadow[0], alpha=shadow[1])]
            )
        self.ax.add_patch(patch)
        return patch

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        color: str,
        lw: float = 1.0,
        alpha: float = 1.0,
        dash: tuple[float, float] | None = None,
    ) -> None:
        style = (0, (_pt(dash[0]), _pt(dash[1]))) if dash else "solid"
        self.ax.plot(
            [x1, x2],
            [y1, y2],
            color=color,
            linewidth=_pt(lw),
            alpha=alpha,
            linestyle=style,
            solid_capstyle="butt",
            zorder=self.z(),
        )

    def circle(
        self,
        cx: float,
        cy: float,
        r: float,
        *,
        fc: str | None = None,
        ec: str | None = None,
        lw: float = 1.0,
        alpha: float = 1.0,
    ) -> None:
        self.ax.add_patch(
            Circle(
                (cx, cy),
                r,
                facecolor=fc if fc else "none",
                edgecolor=ec if ec else "none",
                linewidth=_pt(lw) if ec else 0,
                alpha=alpha,
                zorder=self.z(),
            )
        )

    def crosshair(self, cx: float, cy: float, color: str, *, radius: float = 6.0, arm: float = 6.0) -> None:
        self.circle(cx, cy, radius, ec=color, lw=2)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.line(
                cx + dx * (radius - 1),
                cy + dy * (radius - 1),
                cx + dx * (radius + arm),
                cy + dy * (radius + arm),
                color=color,
                lw=2,
            )

    def save(self, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        self.fig.savefig(target, dpi=100 * SCALE, facecolor="white", metadata={"Software": None})
        plt.close(self.fig)


# --- geometry helpers -----------------------------------------------------------------


def _record_xy(record: Record, width: int, height: int) -> tuple[float, float]:
    return record["x"] / 100 * width, record["y"] / 100 * height


def _blob_points(cx: float, cy: float, radius: float, seed: float, wobble: float = 0.12, lobes: int = 14) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(lobes):
        angle = 2 * math.pi * index / lobes
        scale = 1 + wobble * math.sin(3 * angle + seed) + wobble * 0.55 * math.cos(5 * angle + seed * 1.7)
        points.append((cx + radius * scale * math.cos(angle), cy + radius * scale * math.sin(angle)))
    return points


def _closed_curve(points: Sequence[tuple[float, float]]) -> tuple[list[tuple[float, float]], list[int]]:
    count = len(points)
    verts: list[tuple[float, float]] = [points[0]]
    codes: list[int] = [MplPath.MOVETO]
    for index in range(count):
        p0 = points[(index - 1) % count]
        p1 = points[index]
        p2 = points[(index + 1) % count]
        p3 = points[(index + 2) % count]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        verts.extend([c1, c2, p2])
        codes.extend([MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4])
    verts.append(points[0])
    codes.append(MplPath.CLOSEPOLY)
    return verts, codes


def _rect_edge(cx: float, cy: float, half_w: float, half_h: float, tx: float, ty: float) -> tuple[float, float]:
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    scale = min(half_w / abs(dx) if dx else math.inf, half_h / abs(dy) if dy else math.inf)
    return cx + dx * scale, cy + dy * scale


def _bbox(points: Sequence[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


# --- scenes ---------------------------------------------------------------------------


def districts_png(records: Sequence[Record], target: Path) -> None:
    W, H = 900, 620
    s = Scene(W, H)
    band_colors = {"high": ("#f7a48f", "#dd5f49", "#8d3a2c"), "mid": ("#f9dc9b", "#dfab41", "#8a6516"), "low": ("#d8efcb", "#82b96c", "#3f6b32")}

    sea = s.rect(0, 0, W, H, fc="#d8ecf6")
    s.gradient(sea, 0, 0, W, H, "#d8ecf6", "#a6cfe2", direction="d")
    xs = np.arange(0, W + 1, 2)
    for y in range(18, H, 26):
        s.ax.plot(xs, y + 2.6 * np.sin(xs / 4.1), color="#ffffff", alpha=0.28, linewidth=_pt(1.1), zorder=s.z())

    for cx, cy, radius, seed in [(432, 296, 66, 0.7), (766, 318, 60, 1.9), (112, 258, 54, 2.7), (742, 72, 50, 4.1), (676, 542, 46, 5.2)]:
        verts, codes = _closed_curve(_blob_points(cx, cy, radius, seed, wobble=0.1))
        s.path(verts, codes, fc="#e7eff2", ec="#b9ccd6", lw=1.4, alpha=0.92)

    anchors: dict[str, tuple[float, float]] = {}
    for index, record in enumerate(records):
        cx, cy = _record_xy(record, W, H)
        anchors[str(record["id"])] = (cx, cy)
        light, dark, stroke = band_colors[str(record["band"])]
        points = _blob_points(cx, cy, 88, 0.9 + index * 1.31)
        verts, codes = _closed_curve(points)
        patch = s.path(verts, codes, fc=light, ec=stroke, lw=1.8, shadow=("#123a4a", 0.22))
        bx, by, bw, bh = _bbox(points)
        s.gradient(patch, bx, by, bw, bh, light, dark)
        s.path(verts, codes, ec=stroke, lw=1.8)

    north, east, west, south = (anchors[str(records[i]["id"])] for i in (0, 1, 2, 3))
    river = [
        (north[0], north[1] + 70),
        (north[0] + 60, north[1] + 150),
        (west[0] + 150, west[1] - 120),
        (south[0] - 40, south[1] - 60),
    ]
    s.path(river, [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4], ec="#79b1cc", lw=9, alpha=0.85)
    road = [
        (east[0], east[1] + 70),
        (east[0] - 40, east[1] + 150),
        (south[0] + 60, south[1] - 140),
        (south[0] + 20, south[1] - 66),
    ]
    s.path(road, [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4], ec="#ffffff", lw=3, alpha=0.85, dash=(10, 8))

    for record in records:
        cx, cy = anchors[str(record["id"])]
        _, _, stroke = band_colors[str(record["band"])]
        s.circle(cx, cy, 6.5, fc="#ffffff", ec=stroke, lw=2.4)
        s.text(cx, cy - 24, str(record["name"]), size=19, weight="bold", ha="center", color="#13232c")
        s.text(cx, cy + 30, str(record["id"]), size=11, weight="bold", ha="center", color=stroke)
        s.text(cx, cy + 46, f"rate {record['rate']}", size=11, ha="center", color="#33474f")

    s.rect(20, 8, 24 + _text_width("Harborline districts · synthetic rate survey", 14, "bold"), 34, fc="#0f2b38", r=9, alpha=0.86)
    s.text(32, 31, "Harborline districts · synthetic rate survey", size=14, weight="bold", color="#eaf4f8")

    lx, ly = 28, 506
    s.rect(lx, ly, 266, 86, fc="#ffffff", ec="#8fb0c1", r=10, alpha=0.94)
    s.text(lx + 16, ly + 24, "Rate band", size=12, weight="bold", color="#17303c")
    for (sx, sy, color, label) in [
        (16, 34, "#dd5f49", "high ≥ 14.0"),
        (16, 54, "#dfab41", "mid 8.0 – 13.9"),
        (150, 34, "#82b96c", "low < 8.0"),
    ]:
        s.rect(lx + sx, ly + sy, 20, 13, fc=color, r=3)
        s.text(lx + sx + 28, ly + sy + 11, label, size=11, color="#17303c")
    s.rect(lx + 150, ly + 54, 20, 13, fc="#e7eff2", ec="#b9ccd6", r=3)
    s.text(lx + 178, ly + 65, "unsurveyed", size=11, color="#17303c")

    s.rect(330, 556, 120, 6, fc="#0f2b38", r=2, alpha=0.75)
    s.rect(330, 556, 60, 6, fc="#ffffff", r=2, alpha=0.85)
    s.text(330, 582, "0", size=10, color="#0f2b38")
    s.text(450, 582, "4 km", size=10, ha="center", color="#0f2b38")

    s.circle(846, 52, 26, fc="#ffffff", ec="#0f2b38", lw=1.2, alpha=0.9)
    s.ax.add_patch(Polygon([(846, 34), (853, 58), (846, 53), (839, 58)], closed=True, facecolor="#0f2b38", edgecolor="none", zorder=s.z()))
    s.text(846, 72, "N", size=11, weight="bold", ha="center", color="#0f2b38")
    s.save(target)


def waveform_png(records: Sequence[Record], target: Path) -> None:
    W, H = 900, 320
    left, right, center, amp_px = 64, 872, 160.0, 121.6
    s = Scene(W, H)

    controls = [(left, 0.04), (right, 0.03)]
    controls += [(_record_xy(r, W, H)[0], float(r["amplitude"])) for r in records]
    controls += [(f * W, v) for f, v in ((0.24, 0.44), (0.49, 0.52), (0.71, 0.30), (0.92, 0.11))]
    controls.sort()

    def envelope(x: float) -> float:
        for (x0, v0), (x1, v1) in zip(controls, controls[1:]):
            if x0 <= x <= x1:
                t = (x - x0) / (x1 - x0) if x1 != x0 else 0
                t = t * t * (3 - 2 * t)
                return v0 + (v1 - v0) * t
        return controls[-1][1]

    bg = s.rect(0, 0, W, H, fc="#16212e")
    s.gradient(bg, 0, 0, W, H, "#16212e", "#0a111c")
    s.rect(0, 0, W, 34, fc="#101a26")
    for cx, color in ((24, "#f87171"), (42, "#fbbf24"), (60, "#34d399")):
        s.circle(cx, 17, 5.5, fc=color)
    s.text(80, 22, "lane A · synthetic mix · 2.6 s", size=12, weight="bold", color="#cbd5f5")
    s.text(872, 22, "48 kHz · mono", size=11, ha="right", color="#64748b")

    for y, label in ((center - amp_px, "1.0"), (center - amp_px / 2, "0.5"), (center, "0"), (center + amp_px / 2, "0.5"), (center + amp_px, "1.0")):
        s.line(left, y, right, y, color="#27384c", lw=1, dash=None if label == "0" else (2, 8))
        s.text(left - 10, y + 4, label, size=10, ha="right", color="#5f7387", family=MONO)

    x = float(left)
    while x <= right:
        peak = envelope(x) * amp_px
        texture = 0.55 + 0.45 * abs(math.sin(x * 0.21) * math.cos(x * 0.061 + 1.2))
        bar = max(1.4, peak * texture)
        hue = (x - left) / (right - left)
        color = np.array(to_rgb("#5eead4")) * (1 - hue) + np.array(to_rgb("#a5b4fc")) * hue
        s.rect(x, center - bar, 2, bar * 2, fc=matplotlib.colors.to_hex(color), r=1, alpha=0.9)
        x += 3.4

    xs = np.arange(left, right + 1, 4)
    s.ax.plot(xs, [center - envelope(v) * amp_px for v in xs], color="#e0f2fe", linewidth=_pt(1.4), alpha=0.55, zorder=s.z())

    # Time ruler fitted through the first and last cue so printed ms and cue x agree.
    first, last = min(records, key=lambda r: r["ms"]), max(records, key=lambda r: r["ms"])
    x_first, x_last = _record_xy(first, W, H)[0], _record_xy(last, W, H)[0]
    px_per_ms = (x_last - x_first) / (last["ms"] - first["ms"])
    s.line(left, 272, right, 272, color="#334155", lw=1)
    ms = 0
    while True:
        tick = x_first + (ms - first["ms"]) * px_per_ms
        if tick > right - 6:
            break
        s.line(tick, 272, tick, 280, color="#475569", lw=1)
        s.text(tick, 296, f"{ms}", size=10, ha="center", color="#64748b", family=MONO)
        ms += 500

    for record in records:
        cx, cy = _record_xy(record, W, H)
        s.line(cx, 38, cx, 268, color="#fda4af", lw=1.2, alpha=0.8, dash=(4, 5))
        s.rect(cx - 42, 38, 84, 20, fc="#3f1d2b", ec="#fda4af", lw=1, r=5)
        s.text(cx, 52, str(record["id"]), size=10.5, weight="bold", ha="center", color="#ffe4e6")
        s.crosshair(cx, cy, "#fb7185", radius=6, arm=5)
        label = f"{record['ms']} ms"
        label_w = 12 + _text_width(label, 10, family=MONO)
        s.rect(cx - label_w / 2, cy + 14, label_w, 16, fc="#0a111c", r=4, alpha=0.8)
        s.text(cx, cy + 26, label, size=10, ha="center", color="#fecdd3", family=MONO)
    s.save(target)


def grid_frame_png(records: Sequence[Record], target: Path) -> None:
    W, H = 900, 560
    columns = {"A": (81.0, 315.0), "B": (315.0, 549.0), "C": (549.0, 783.0), "D": (783.0, 872.0)}
    rows = {1: (72.8, 240.8), 2: (240.8, 408.8), 3: (408.8, 520.0)}
    s = Scene(W, H)

    s.rect(0, 0, W, H, fc="#ece5d8")
    s.rect(16, 4, 868, 552, fc="#ffffff", ec="#d5cab7", r=14, shadow=("#8a7b64", 0.28))
    s.text(28, 32, "fx", size=13, weight="bold", color="#8a7f6d", family=MONO)
    s.rect(52, 12, 820, 34, fc="#fbfaf6", ec="#ded4c2", r=8)
    s.text(66, 34, "=SUM(A1:A2)", size=14, color="#1d4f91", family=MONO)
    s.text(862, 34, "B2", size=11, ha="right", color="#9a8f7c", family=MONO)
    header = s.rect(28, 46, 844, 27, fc="#f8f6f1", ec="#ddd3c1")
    s.gradient(header, 28, 46, 844, 27, "#f8f6f1", "#e8e1d4")
    side = s.rect(28, 46, 53, 474, fc="#f8f6f1", ec="#ddd3c1")
    s.gradient(side, 28, 46, 53, 474, "#f8f6f1", "#e8e1d4")

    for name, (x0, x1) in columns.items():
        s.line(x0, 46, x0, 520, color="#e6dccb", lw=1)
        s.text((x0 + x1) / 2, 65, name, size=12, weight="bold", ha="center", color="#5a5142")
    for number, (y0, y1) in rows.items():
        s.line(28, y0, 872, y0, color="#e6dccb", lw=1)
        s.text(54, (min(y1, 520) + y0) / 2 + 5, str(number), size=12, ha="center", color="#7a7161")

    for record in records:
        cx, cy = _record_xy(record, W, H)
        label = str(record["label"])
        x0, x1 = columns[label[0]]
        y0, y1 = rows[int(label[1])]
        formula = str(record["kind"]) == "formula"
        s.rect(x0 + 1, y0 + 1, x1 - x0 - 2, y1 - y0 - 2, fc="#e8f1ff" if formula else "#ffffff", ec="#7aa2e3" if formula else "#efe7d9", lw=2 if formula else 1)
        s.text(cx, cy - 30, str(record["id"]), size=11, ha="center", color="#8a8073")
        if formula:
            s.text(cx, cy + 6, "=SUM(A1:A2)", size=20, weight="bold", ha="center", color="#1d4f91", family=MONO)
            s.text(cx, cy + 32, "pending commit", size=11, ha="center", color="#4d78bb")
        else:
            s.text(cx, cy + 10, str(record["value"]), size=30, weight="bold", ha="center", color="#1f2933", family=MONO)

    s.rect(28, 520, 844, 28, fc="#f6f2ea", ec="#e2d9c8")
    s.text(42, 539, "Sheet1 · protected local workbook · 4 seeded cells", size=11, color="#7a7166")
    s.text(862, 539, "ready", size=11, ha="right", color="#7a7166")
    s.save(target)


def before_after_png(records: Sequence[Record], target: Path) -> None:
    W, H = 900, 520
    s = Scene(W, H)
    s.rect(0, 0, 450, H, fc="#e9eef5")
    s.rect(450, 0, 450, H, fc="#f7efe7")
    s.line(450, 0, 450, H, color="#cbb9a6", lw=1.5, dash=(7, 6))

    def pane(x0: float, tone: str, accent: str, chrome: str, label: str, url: str) -> None:
        s.rect(x0, 56, 410, 436, fc=tone, ec=accent, lw=1.4, r=14, shadow=("#475569", 0.18))
        s.rect(x0, 56, 410, 34, fc=chrome, r=14)
        s.rect(x0, 76, 410, 14, fc=chrome)
        for dx, color in ((20, "#f87171"), (34, "#fbbf24"), (48, "#34d399")):
            s.circle(x0 + dx, 73, 4.5, fc=color)
        s.rect(x0 + 64, 64, 320, 18, fc="#ffffff", r=9, alpha=0.16)
        s.text(x0 + 78, 77, url, size=10, color="#e2e8f0", family=MONO)
        s.text(x0 + 4, 44, label, size=13, weight="bold", color=accent)

    pane(20, "#f8fafc", "#475569", "#1e293b", "BEFORE · checkout v12", "shop.local/cart")
    pane(470, "#fffaf4", "#9a3412", "#7c2d12", "AFTER · checkout v13", "shop.local/cart")

    # before page
    for x, fill, text_color, label in ((44, "#64748b", "#f8fafc", "Home"), (118, "#94a3b8", "#f8fafc", "Bags"), (192, "#cbd5e1", "#1e293b", "Sale")):
        s.rect(x, 112, 66, 20, fc=fill, r=6)
        s.text(x + 10, 126, label, size=10, color=text_color)
    hero = s.rect(44, 150, 362, 120, fc="#dbe3ec", r=10)
    s.gradient(hero, 44, 150, 362, 120, "#dbe3ec", "#9aa8b8", direction="d")
    s.text(60, 222, "Canvas tote", size=18, weight="bold", color="#0f172a")
    s.text(60, 246, "in stock · ships in 3 days", size=11, color="#334155")
    s.rect(44, 288, 150, 40, fc="#94a3b8", r=9)
    s.text(70, 313, "Add to bag", size=13, weight="bold", color="#0f172a")
    s.rect(44, 392, 230, 72, fc="#e2e8f0", r=10)
    s.text(60, 418, "account · help · returns", size=12, color="#334155")
    s.text(60, 440, "shipping policy", size=11, color="#64748b")

    # after page (nav row intentionally absent)
    hero2 = s.rect(494, 150, 362, 110, fc="#bfdbfe", r=10)
    s.gradient(hero2, 494, 150, 362, 110, "#bfdbfe", "#2563eb", direction="d")
    s.text(510, 226, "Canvas tote", size=18, weight="bold", color="#ffffff")
    s.text(510, 246, "in stock · ships in 3 days", size=11, color="#e0f2fe")
    s.rect(546, 136, 150, 40, fc="#2563eb", r=9)
    s.text(572, 161, "Add to bag", size=13, weight="bold", color="#ffffff")
    s.rect(560, 288, 200, 76, fc="#fdba74", r=10)
    s.text(578, 316, "price 42", size=24, weight="bold", color="#7c2d12")
    s.text(578, 340, "was 28 · palette shifted", size=11, color="#9a3412")
    s.rect(494, 404, 330, 16, fc="#fde7d3", r=6)
    s.rect(494, 452, 230, 16, fc="#fde7d3", r=6)

    severity_color = {"review": "#dc2626", "watch": "#d97706", "info": "#0369a1"}
    box_half = {"DIFF-NAV": (118.0, 30.0)}
    for record in records:
        cx, cy = _record_xy(record, W, H)
        color = severity_color[str(record["severity"])]
        half_w, half_h = box_half.get(str(record["id"]), (86.0, 34.0))
        label = str(record["id"])
        badge_w = 16 + _text_width(label, 10.5, "bold")
        badge_y = cy - half_h - 21 if cy - half_h >= 104 else cy + half_h + 2
        s.rect(cx - half_w, cy - half_h, half_w * 2, half_h * 2, fc=None, ec=color, lw=2, r=10, dash=(6, 5), alpha=0.95)
        s.rect(cx - half_w, badge_y, badge_w, 19, fc=color, r=5)
        s.text(cx - half_w + 8, badge_y + 13.5, label, size=10.5, weight="bold", color="#ffffff")
        s.crosshair(cx, cy, color)

    # severity legend (colors are the only carrier of severity)
    lx = 20
    s.text(lx, 511, "severity", size=10.5, weight="bold", color="#475569")
    for offset, (name, color) in enumerate(severity_color.items()):
        x = lx + 70 + offset * 92
        s.rect(x, 500, 14, 14, fc=color, r=3)
        s.text(x + 20, 511, name, size=10.5, color="#475569")
    s.save(target)


def graph_png(records: Sequence[Record], target: Path, edges: Sequence[tuple[str, str]]) -> None:
    W, H = 900, 560
    half_w, half_h = 74.0, 39.0
    kind_color = {"source": "#10b981", "bridge": "#6366f1", "sink": "#f43f5e"}
    s = Scene(W, H)
    bg = s.rect(0, 0, W, H, fc="#f8f7ff")
    s.gradient(bg, 0, 0, W, H, "#f8f7ff", "#eae6fd", direction="d")
    for gx in range(0, W + 1, 60):
        s.line(gx, 0, gx, H, color="#ded7fb", lw=1)
    for gy in range(0, H + 1, 60):
        s.line(0, gy, W, gy, color="#ded7fb", lw=1)

    anchors = {str(r["id"]): _record_xy(r, W, H) for r in records}
    for source, target_id in edges:
        sx, sy = anchors[source]
        tx, ty = anchors[target_id]
        start = _rect_edge(sx, sy, half_w + 6, half_h + 6, tx, ty)
        end = _rect_edge(tx, ty, half_w + 10, half_h + 10, sx, sy)
        arrow = FancyArrowPatch(
            start,
            end,
            connectionstyle="arc3,rad=-0.15",
            arrowstyle="-|>,head_length=8,head_width=4",
            mutation_scale=1,
            color="#5b4d8a",
            linewidth=_pt(3),
            alpha=0.85,
            zorder=s.z(),
        )
        s.ax.add_patch(arrow)

    for record in records:
        cx, cy = anchors[str(record["id"])]
        kind = str(record["kind"])
        emphasis = kind == "bridge"
        s.rect(cx - half_w, cy - half_h, half_w * 2, half_h * 2, fc="#ede9fe" if emphasis else "#ffffff", ec="#43328a", lw=2.6 if emphasis else 1.8, r=18, shadow=("#3b2f6b", 0.2))
        s.circle(cx - half_w + 22, cy, 10, fc=kind_color[kind])
        s.text(cx - half_w + 40, cy - 6, str(record["id"]), size=10.5, weight="bold", color="#5b5382")
        s.text(cx - half_w + 40, cy + 14, str(record["label"]), size=16, weight="bold", color="#1e1b4b")

    s.rect(24, 486, 330, 46, fc="#ffffff", ec="#c7bcf5", r=10, alpha=0.94)
    s.text(36, 500, "node kind", size=10, weight="bold", color="#43328a")
    for offset, (name, color) in enumerate(kind_color.items()):
        x = 46 + offset * 94
        s.circle(x, 518, 7, fc=color)
        s.text(x + 14, 522, name, size=11, color="#43328a")
    s.save(target)


def print_pages_png(records: Sequence[Record], target: Path) -> None:
    W, H = 900, 640
    page_w, page_h = 176.0, 228.0
    s = Scene(W, H)
    s.rect(0, 0, W, H, fc="#d7cdbc")
    s.rect(0, 0, W, 46, fc="#c3b199")
    s.text(24, 29, "Harbor Review · print preview", size=13, weight="bold", color="#3f3527")
    s.text(876, 29, "letter · 100% · 4 pages", size=11, ha="right", color="#5b4c3a")
    for ruler_x in range(60, 880, 40):
        s.line(ruler_x, 52, ruler_x, 60, color="#b3a289", lw=1)

    for record in records:
        cx, cy = _record_xy(record, W, H)
        x0, y0 = cx - page_w / 2, cy - page_h / 2
        s.rect(x0, y0, page_w, page_h, fc="#fffdf8", ec="#c8b79c", r=3, shadow=("#7d6c56", 0.32))
        s.line(x0 + 16, y0 + 26, x0 + page_w - 16, y0 + 26, color="#e3d8c6", lw=1)
        s.text(x0 + 16, y0 + 20, f"Harbor Review / {record['page']}", size=8.5, color="#8a7760")
        s.text(x0 + 16, y0 + 52, str(record["title"]), size=17, color="#20242b", family=SERIF)
        s.text(x0 + 16, y0 + 68, f"{record['id']} · {record['words']} words", size=8.5, color="#94836c")
        s.text(cx, y0 + page_h - 12, str(record["page"]), size=9, ha="center", color="#94836c")
        line_top = y0 + 84
        if str(record["title"]) == "Methods":
            s.rect(x0 + 16, line_top, page_w - 32, 52, fc="#f2ebdf", ec="#ddcfb8")
            s.text(x0 + 24, line_top + 30, "Fig. 2 · sampling frame", size=8.5, color="#7d6c56")
            line_top += 62
        for row in range(max(2, int(round(int(record["words"]) / 45)))):
            line_y = line_top + row * 13
            if line_y > y0 + page_h - 26:
                break
            span = page_w - 32 if row % 3 != 2 else (page_w - 32) * 0.68
            s.rect(x0 + 16, line_y, span, 5, fc="#e7ddd0", r=2)
    s.save(target)


BUILDERS: dict[str, Callable[..., None]] = {
    "districts.png": districts_png,
    "waveform.png": waveform_png,
    "grid-frame.png": grid_frame_png,
    "before-after.png": before_after_png,
    "graph.png": graph_png,
    "print-pages.png": print_pages_png,
}

DESIGN_SIZE: dict[str, tuple[int, int]] = {
    "districts.png": (900, 620),
    "waveform.png": (900, 320),
    "grid-frame.png": (900, 560),
    "before-after.png": (900, 520),
    "graph.png": (900, 560),
    "print-pages.png": (900, 640),
}


def render(asset: str, records: Sequence[Record], target: Path, **kwargs: Any) -> None:
    """Render one protected PNG from the task's full (hidden) records."""
    BUILDERS[asset](records, target, **kwargs)
