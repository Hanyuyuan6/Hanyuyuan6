#!/usr/bin/env python3
"""Build the profile README's hero banner and project cards (light and dark SVGs).

All text is shaped with HarfBuzz and outlined from Noto Sans (SIL OFL 1.1), so the
images look identical on every system and need no web fonts. The banner's bars are
the first 2D Hadamard measurements (sequency order, signed square root for display)
of the 16x16 three-class mask drawn beside them: the 1D-to-2D "lift" this research
is about.

    pip install fonttools==4.66.1 uharfbuzz==0.56.3
    python scripts/build_assets.py --fonts ../hanyuyuan6.github.io/fonts
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

OUT = Path(__file__).resolve().parent.parent / "assets"
# One dark design for both GitHub themes: README files render in "markdown" mode,
# which splits a <picture> wrapped in a link, so theme switching and clickable cards
# cannot both be relied on. A dark banner and dark cards read well on either page.
THEME = {"bg0": "#0b1220", "bg1": "#132438", "border": "#2a3a4d", "ink": "#eef3f8", "muted": "#9aa7b5",
         "accent": "#7db7e8", "accent2": "#8fe3d4", "cell": "#1b2735", "cyto": "#2f6188", "nucleus": "#8cc4f0",
         "card": "#101a26", "chip": "#18304a", "scan": "#8cc4f0"}
LANGUAGE = {"Python": "#3572A5", "PyTorch": "#ee4c2c", "MATLAB": "#e16737"}
CARDS = [
    {"slug": "stsf-tpls", "kind": "PAPER + CODE", "name": "STSF-TPLS", "language": "PyTorch", "chip": "arXiv 2026", "motif": "mask",
     "text": "Segment straight from single-pixel measurements: near-constant accuracy down to 0.78% sampling."},
    {"slug": "remote-gpu-trainer", "kind": "OPEN-SOURCE TOOL", "name": "remote-gpu-trainer", "language": "Python", "chip": "60+ stars", "star": True, "motif": "pipeline",
     "text": "Agent skill for Claude Code and Codex: run, verify and deliver GPU experiments."},
    {"slug": "shsi", "kind": "PAPER + CODE", "name": "SHSI", "language": "MATLAB", "chip": "Optics Express 2025", "motif": "sparse",
     "text": "Hadamard patterns with tunable sparsity: robust through scattering and noise, low memory."},
    {"slug": "ldgi", "kind": "PAPER + CODE", "name": "LDGI", "language": "MATLAB", "chip": "Opt. Commun. 2025", "motif": "lines",
     "text": "Loop differential ghost imaging for optical phased arrays: orders-of-magnitude gains."},
]


class Face:
    """One font file: HarfBuzz for shaping (kerning), fontTools for outlines."""

    def __init__(self, path: Path):
        self.tt = TTFont(path)
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        self.upem = self.tt["head"].unitsPerEm

    def shape(self, text: str):
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.guess_segment_properties()
        hb.shape(self.font, buffer, {"kern": True, "liga": True})
        return list(zip(buffer.glyph_infos, buffer.glyph_positions))

    def width(self, text: str, size: float, tracking: float = 0) -> float:
        runs = self.shape(text)
        return sum(p.x_advance for _, p in runs) * size / self.upem + tracking * max(len(runs) - 1, 0)

    def path(self, text: str, x: float, y: float, size: float, tracking: float = 0) -> str:
        scale = size / self.upem
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        cursor = 0.0
        for info, position in self.shape(text):
            name = self.order[info.codepoint]
            dx = x + (cursor + position.x_offset) * scale
            dy = y - position.y_offset * scale
            self.glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, dx, dy)))
            cursor += position.x_advance + tracking / scale
        return pen.getCommands()


def wrap(face: Face, text: str, size: float, width: float) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and face.width(trial, size) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def cell_mask(n: int = 16) -> list[list[int]]:
    """A white-blood-cell-like mask: 0 background, 1 cytoplasm, 2 lobed nucleus."""
    c = (n - 1) / 2
    lobes = [(c - 1.7, c - 0.9, 2.15), (c + 1.6, c - 1.2, 1.95), (c + 0.3, c + 1.9, 2.05)]
    mask = []
    for r in range(n):
        row = []
        for q in range(n):
            wobble = 0.35 * math.sin(3 * math.atan2(r - c, q - c))
            if any(math.hypot(q - x, r - y) <= rad for x, y, rad in lobes):
                row.append(2)
            elif math.hypot(q - c, r - c) <= 6.5 + wobble:
                row.append(1)
            else:
                row.append(0)
        mask.append(row)
    return mask


def hadamard_measurements(mask: list[list[int]], count: int) -> list[float]:
    """2D Walsh-Hadamard coefficients H f H^T of the mask, lowest total sequency first
    (as a single-pixel camera would acquire them), DC dropped, signed square root."""
    n = len(mask)
    f = [[{0: 0.0, 1: 0.55, 2: 1.0}[v] for v in row] for row in mask]
    h = [[-1 if bin(i & j).count("1") % 2 else 1 for j in range(n)] for i in range(n)]
    sequency = [sum(h[i][j] != h[i][j + 1] for j in range(n - 1)) for i in range(n)]
    pairs = sorted(((u, v) for u in range(n) for v in range(n)),
                   key=lambda uv: (sequency[uv[0]] + sequency[uv[1]], max(sequency[uv[0]], sequency[uv[1]]), uv))
    y = [sum(h[u][r] * h[v][q] * f[r][q] for r in range(n) for q in range(n)) for u, v in pairs[1:count + 1]]
    peak = max(abs(value) for value in y)
    return [math.copysign(math.sqrt(abs(value) / peak), value) for value in y]


def hero(faces: dict[str, Face], theme: dict[str, str]) -> str:
    W, H = 1280, 340
    bold, regular = faces["bold"], faces["regular"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">',
        "<title id=\"t\">Yuyuan Han — computational imaging and physics-aware learning. Learning to sense the physical world.</title>",
        "<defs>",
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{theme["bg0"]}"/><stop offset="1" stop-color="{theme["bg1"]}"/></linearGradient>',
        f'<linearGradient id="ink" gradientUnits="userSpaceOnUse" x1="64" y1="0" x2="620" y2="0"><stop offset="0" stop-color="{theme["accent"]}"/><stop offset="1" stop-color="{theme["accent2"]}"/></linearGradient>',
        f'<linearGradient id="bars" gradientUnits="userSpaceOnUse" x1="744" y1="0" x2="962" y2="0"><stop offset="0" stop-color="{theme["accent"]}"/><stop offset="1" stop-color="{theme["accent2"]}"/></linearGradient>',
        f'<linearGradient id="scan" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{theme["scan"]}" stop-opacity="0"/><stop offset=".5" stop-color="{theme["scan"]}" stop-opacity=".55"/><stop offset="1" stop-color="{theme["scan"]}" stop-opacity="0"/></linearGradient>',
        f'<clipPath id="card"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18"/></clipPath>',
        "</defs>",
        # The scan band starts off-canvas, so a static render (no animation) is complete.
        "<style>.scan{animation:sweep 2.6s cubic-bezier(.4,0,.2,1) .4s 1 both}"
        "@keyframes sweep{from{transform:translateX(-160px)}to{transform:translateX(1440px)}}"
        "@media (prefers-reduced-motion:reduce){.scan{animation:none}}</style>",
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="url(#bg)" stroke="{theme["border"]}" stroke-width="1.5"/>',
    ]
    x = 64
    parts.append(f'<path fill="{theme["accent"]}" d="{bold.path("COMPUTATIONAL IMAGING · PHYSICS-AWARE LEARNING", x, 86, 14, tracking=2.2)}"/>')
    parts.append(f'<path fill="{theme["ink"]}" d="{bold.path("Yuyuan Han", x - 2, 156, 66, tracking=-1.2)}"/>')
    parts.append(f'<path fill="url(#ink)" d="{regular.path("Learning to sense the physical world.", x, 206, 31, tracking=-0.3)}"/>')
    parts.append(f'<path fill="{theme["muted"]}" d="{regular.path("PhD student, Xi’an Jiaotong University", x, 252, 18)}"/>')
    parts.append(f'<path fill="{theme["muted"]}" d="{regular.path("Visiting PhD student, Politecnico di Milano", x, 280, 18)}"/>')
    # 1D measurements: signed bars around a baseline.
    mask = cell_mask()
    values = hadamard_measurements(mask, 44)
    left, mid, amp, step, bar = 744, 168, 70, 5.0, 3.0
    bars = "".join(
        f'<rect x="{left + i * step:.1f}" y="{mid - max(abs(v) * amp, 1.5) if v >= 0 else mid:.1f}" width="{bar}" height="{max(abs(v) * amp, 1.5):.1f}" rx="1"/>'
        for i, v in enumerate(values)
    )
    parts.append(f'<g fill="url(#bars)">{bars}</g>')
    parts.append(f'<line x1="{left - 6}" y1="{mid}" x2="{left + len(values) * step + 2}" y2="{mid}" stroke="{theme["border"]}" stroke-width="1"/>')
    # The lift arrow.
    ax0, ax1 = left + len(values) * step + 18, left + len(values) * step + 58
    parts.append(f'<path d="M{ax0} {mid}H{ax1 - 8}" stroke="{theme["muted"]}" stroke-width="2" stroke-linecap="round"/>')
    parts.append(f'<path d="M{ax1 - 12} {mid - 6}L{ax1 - 4} {mid}L{ax1 - 12} {mid + 6}" fill="none" stroke="{theme["muted"]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append(f'<path fill="{theme["muted"]}" d="{faces["italic"].path("lift", ax0 + 8, mid - 12, 14)}"/>')
    # 2D understanding: the three-class mask.
    cell, gap = 10.0, 1.6
    gx, gy = W - 64 - 16 * (cell + gap) + gap, mid - (16 * (cell + gap) - gap) / 2
    colours = {0: theme["cell"], 1: theme["cyto"], 2: theme["nucleus"]}
    for value in (0, 1, 2):
        rects = "".join(
            f'<rect x="{gx + q * (cell + gap):.1f}" y="{gy + r * (cell + gap):.1f}" width="{cell}" height="{cell}" rx="2"/>'
            for r, row in enumerate(mask) for q, v in enumerate(row) if v == value
        )
        parts.append(f'<g fill="{colours[value]}">{rects}</g>')
    parts.append(f'<path fill="{theme["muted"]}" d="{regular.path("1D measurements", left, 292, 13)}"/>')
    label = "2D understanding"
    parts.append(f'<path fill="{theme["muted"]}" d="{regular.path(label, W - 64 - regular.width(label, 13), 292, 13)}"/>')
    parts.append(f'<g clip-path="url(#card)"><rect class="scan" x="0" y="0" width="140" height="{H}" fill="url(#scan)"/></g>')
    parts.append("</svg>\n")
    return "".join(parts)


def motif(kind: str, theme: dict[str, str], x: float, y: float) -> str:
    """A 36-px emblem in the card's top-right corner."""
    out = []
    if kind == "mask":
        m = cell_mask(8)
        for r, row in enumerate(m):
            for q, v in enumerate(row):
                colour = {0: theme["cell"], 1: theme["cyto"], 2: theme["nucleus"]}[v]
                out.append(f'<rect x="{x + q * 4.5:.1f}" y="{y + r * 4.5:.1f}" width="3.8" height="3.8" rx=".8" fill="{colour}"/>')
    elif kind == "sparse":
        for r in range(8):
            for q in range(8):
                on = (bin(r & q).count("1") % 2 == 0) and ((r * 3 + q * 5) % 4 == 0)
                out.append(f'<rect x="{x + q * 4.5:.1f}" y="{y + r * 4.5:.1f}" width="3.8" height="3.8" rx=".8" fill="{theme["accent"] if on else theme["cell"]}"/>')
    elif kind == "lines":
        for q in range(8):
            opacity = 0.25 + 0.75 * (0.5 + 0.5 * math.cos(q * 1.3))
            out.append(f'<rect x="{x + q * 4.5:.1f}" y="{y}" width="3.2" height="35.6" rx="1.2" fill="{theme["accent"]}" fill-opacity="{opacity:.2f}"/>')
    else:  # run -> verify -> deliver
        cy = y + 18
        out.append(f'<path d="M{x + 4} {cy}H{x + 32}" stroke="{theme["cyto"]}" stroke-width="2"/>')
        for i, filled in enumerate((False, False, True)):
            cx = x + 4 + i * 14
            out.append(f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="{theme["accent"] if filled else theme["card"]}" stroke="{theme["accent"]}" stroke-width="2"/>')
    return "".join(out)


def card(faces: dict[str, Face], theme: dict[str, str], spec: dict[str, str]) -> str:
    W, H = 400, 150
    bold, regular = faces["bold"], faces["regular"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">',
        f'<title id="t">{spec["name"]}: {spec["text"]}</title>',
        f'<defs><linearGradient id="c" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{theme["card"]}"/><stop offset="1" stop-color="{theme["bg1"]}"/></linearGradient></defs>',
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="url(#c)" stroke="{theme["border"]}" stroke-width="1.5"/>',
        f'<path fill="{theme["accent"]}" d="{bold.path(spec["kind"], 24, 36, 11, tracking=1.4)}"/>',
        f'<path fill="{theme["ink"]}" d="{bold.path(spec["name"], 24, 64, 21, tracking=-0.2)}"/>',
        motif(spec["motif"], theme, W - 24 - 36, 20),
    ]
    for i, line in enumerate(wrap(regular, spec["text"], 13.5, W - 48)[:2]):
        parts.append(f'<path fill="{theme["muted"]}" d="{regular.path(line, 24, 90 + i * 19, 13.5)}"/>')
    parts.append(f'<circle cx="29" cy="129" r="5" fill="{LANGUAGE[spec["language"]]}"/>')
    parts.append(f'<path fill="{theme["muted"]}" d="{regular.path(spec["language"], 41, 133.5, 12.5)}"/>')
    icon = 15 if spec.get("star") else 0  # Noto Sans has no U+2605, so the star is drawn
    chip_w = bold.width(spec["chip"], 12) + 22 + icon
    cx = W - 24 - chip_w
    parts.append(f'<rect x="{cx:.1f}" y="117" width="{chip_w:.1f}" height="24" rx="12" fill="{theme["chip"]}"/>')
    if icon:
        sx, sy, outer, inner = cx + 16, 129, 5.6, 2.4
        points = " ".join(f"{sx + (outer if k % 2 == 0 else inner) * math.sin(k * math.pi / 5):.2f},{sy - (outer if k % 2 == 0 else inner) * math.cos(k * math.pi / 5):.2f}" for k in range(10))
        parts.append(f'<polygon points="{points}" fill="{theme["accent"]}"/>')
    parts.append(f'<path fill="{theme["accent"]}" d="{bold.path(spec["chip"], cx + 11 + icon, 133.5, 12)}"/>')
    parts.append("</svg>\n")
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fonts", type=Path, required=True, help="Folder with NotoSans-Regular/Bold/Italic.ttf")
    args = parser.parse_args()
    faces = {k: Face(args.fonts / f"NotoSans-{v}.ttf") for k, v in (("regular", "Regular"), ("bold", "Bold"), ("italic", "Italic"))}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hero.svg").write_text(hero(faces, THEME), encoding="utf-8", newline="\n")
    for spec in CARDS:
        (OUT / f"card-{spec['slug']}.svg").write_text(card(faces, THEME, spec), encoding="utf-8", newline="\n")
    for path in sorted(OUT.glob("*.svg")):
        print(f"{path.name}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
