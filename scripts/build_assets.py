#!/usr/bin/env python3
"""Build the profile README's banner and project cards.

The only graphic is one signal: data/portrait-signal.json, the first 1024 two-dimensional
Walsh-Hadamard measurements (sequency order, DC term omitted, normalised to [-1, 1]) that a
single-pixel camera would record of the public 64x64 portrait on hanyuyuan6.github.io.
Traces pass through real samples at their real, linear amplitudes. Between samples they
follow a shape-preserving (monotone) cubic, so every peak and trough drawn is a measured
value and nothing is smoothed away. The amber square marks the newest sample: the pixel.

Text is shaped with HarfBuzz and outlined from Noto Sans (SIL OFL 1.1), so the SVGs embed
no fonts and render the same everywhere. One dark design serves both GitHub themes: README
files render in "markdown" mode, which splits a <picture> wrapped in a link.

    pip install fonttools==4.66.1 uharfbuzz==0.56.3
    python scripts/build_assets.py --fonts ../hanyuyuan6.github.io/fonts

Every build re-checks its own geometry (no text touches the signal or other text, all ink
inside the margins), contrast, file size and self-containment, and stress-tests the banner
with longer positioning lines.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
from pathlib import Path
from xml.sax.saxutils import escape

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIGNAL = json.loads((ROOT / "data" / "portrait-signal.json").read_text(encoding="utf-8"))["values"]

# Brand palette, unchanged. Rule: type is neutral (ink, muted); colour belongs to the data
# (the trace runs blue -> mint, earliest to latest sample); amber is reserved for the pixel.
C = {"bg0": "#0b1220", "bg1": "#132438", "border": "#2a3a4d", "ink": "#eef3f8", "muted": "#9aa7b5",
     "blue": "#7db7e8", "mint": "#8fe3d4", "amber": "#ffd166"}

NAME = "Yuyuan Han"
EYEBROW = "Single-pixel imaging · Image-free sensing"           # set in capitals, 41 characters
LINE = "Teaching machines to see from raw measurements, not images."
AFFILIATIONS = ("PhD student, Xi’an Jiaotong University", "Visiting PhD student, Politecnico di Milano")
STRESS_LINES = (  # any positioning line of up to nine words must fit both banners
    "Teaching machines to see with a single pixel.",
    "Perception from single-pixel measurements, without ever forming images.",
    "Machine perception learned directly from compressive single-pixel optical measurements.",
    "Understanding scenes through compressive measurement-domain perception without reconstructing images.",
)
CARDS = [  # description line breaks are set by hand (sense first), then checked to fit
    {"slug": "stsf-tpls", "kind": "Paper + code", "name": "STSF-TPLS", "venue": "arXiv 2026", "language": "PyTorch",
     "text": ("Segment straight from single-pixel measurements:", "near-constant accuracy down to 0.78% sampling.")},
    {"slug": "remote-gpu-trainer", "kind": "Open-source tool", "name": "remote-gpu-trainer", "venue": "60+ stars",
     "language": "Python", "text": ("Agent skill for Claude Code and Codex:", "run, verify and deliver GPU experiments.")},
    {"slug": "shsi", "kind": "Paper + code", "name": "SHSI", "venue": "Optics Express 2025", "language": "MATLAB",
     "text": ("Hadamard patterns with tunable sparsity:", "robust through scattering and noise, low memory.")},
    {"slug": "ldgi", "kind": "Paper + code", "name": "LDGI", "venue": "Optics Communications 2025", "language": "MATLAB",
     "text": ("Loop differential ghost imaging for", "optical phased arrays: orders-of-magnitude gains.")},
]

# Optical margin: letters that touch the margin only with a point or a curve hang slightly
# past it so the column looks straight (fractions of the type size).
HANG = {"Y": 0.025, "A": 0.02, "V": 0.02, "W": 0.02, "T": 0.012, "O": 0.008, "C": 0.008, "G": 0.008, "S": 0.006}
CAP_HYPHEN_RAISE = 89  # font units: lifts the hyphen from x-height centre (268) to cap centre (357)


class Face:
    """One font file: HarfBuzz shaping with OpenType features, fontTools outlines and ink bounds."""

    def __init__(self, path: Path):
        self.tt = TTFont(path)
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        self.upem = self.tt["head"].unitsPerEm

    def shape(self, text: str, features: dict | None = None):
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.guess_segment_properties()
        hb.shape(self.font, buffer, {"kern": True, "liga": True, **(features or {})})
        return list(zip(buffer.glyph_infos, buffer.glyph_positions))

    def _glyphs(self, text, x, y, size, tracking, features):
        scale = size / self.upem
        cursor = 0.0
        for info, pos in self.shape(text, features):
            k = info.cluster
            lift = 0
            if text[k] == "-" and k > 0 and k + 1 < len(text) and text[k - 1].isupper() and text[k + 1].isupper():
                lift = CAP_HYPHEN_RAISE
            transform = (scale, 0, 0, -scale, x + (cursor + pos.x_offset) * scale, y - (pos.y_offset + lift) * scale)
            yield self.order[info.codepoint], transform
            cursor += pos.x_advance + tracking / scale

    def path(self, text, x, y, size, tracking=0.0, features=None):
        digits = 2 if size < 20 else 1
        pen = SVGPathPen(self.glyphs, ntos=lambda v: (f"{v:.{digits}f}".rstrip("0").rstrip(".") or "0"))
        for name, t in self._glyphs(text, x, y, size, tracking, features):
            self.glyphs[name].draw(TransformPen(pen, t))
        return pen.getCommands()

    def ink(self, text, x, y, size, tracking=0.0, features=None):
        pen = BoundsPen(self.glyphs)
        for name, t in self._glyphs(text, x, y, size, tracking, features):
            self.glyphs[name].draw(TransformPen(pen, t))
        return pen.bounds  # (left, top, right, bottom) in SVG coordinates

    def width(self, text, size, tracking=0.0, features=None):
        runs = self.shape(text, features)
        return sum(p.x_advance for _, p in runs) * size / self.upem + tracking * max(len(runs) - 1, 0)


class Canvas:
    """Collects SVG elements plus the ink box of every text run and graphic, for the checks."""

    def __init__(self, width, height, uid):
        self.w, self.h, self.uid = width, height, uid  # uid prefixes ids: SVGs may share a page
        self.parts: list[str] = []
        self.boxes: list[tuple[str, str, tuple[float, float, float, float]]] = []  # (kind, label, box)

    def text(self, face, s, x, y, size, fill, *, tracking=0.0, features=None, align="left"):
        """Place a run so its ink (not its advance box) starts at x, or ends at x when align='right'."""
        left, _, right, _ = face.ink(s, 0, 0, size, tracking, features)
        x0 = x - left - HANG.get(s[0], 0) * size if align == "left" else x - right
        self.parts.append(f'<path fill="{fill}" d="{face.path(s, x0, y, size, tracking, features)}"/>')
        self.boxes.append(("text", s, face.ink(s, x0, y, size, tracking, features)))

    def trace(self, points, width, head=0.0):
        self.parts.append(f'<path d="{monotone_path(points)}" fill="none" stroke="url(#{self.uid}-sig)" '
                          f'stroke-width="{width:g}" stroke-linejoin="round" stroke-linecap="butt"/>')
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        half = width / 2  # monotone cubic: the curve never leaves the samples' range
        self.boxes.append(("signal", "trace", (min(xs), min(ys) - half, max(xs), max(ys) + half)))
        if head:
            hx, hy = points[-1]
            self.parts.append(f'<rect x="{hx - head / 2:.2f}" y="{hy - head / 2:.2f}" width="{head:g}" height="{head:g}" fill="{C["amber"]}"/>')
            self.boxes.append(("signal", "pixel", (hx - head / 2, hy - head / 2, hx + head / 2, hy + head / 2)))


def trace_points(values, x0, x1, zero, amp):
    step = (x1 - x0) / (len(values) - 1)
    return [(x0 + i * step, zero - v * amp) for i, v in enumerate(values)]


def monotone_path(points) -> str:
    """Fritsch-Carlson monotone cubic through every sample: no overshoot, no new extrema."""
    n, h = len(points), points[1][0] - points[0][0]
    ys = [p[1] for p in points]
    d = [(ys[k + 1] - ys[k]) / h for k in range(n - 1)]
    m = [d[0]] + [0.0 if d[k - 1] * d[k] <= 0 else (d[k - 1] + d[k]) / 2 for k in range(1, n - 1)] + [d[-1]]
    for k in range(n - 1):
        if d[k] == 0:
            m[k] = m[k + 1] = 0.0
            continue
        a, b = m[k] / d[k], m[k + 1] / d[k]
        if a * a + b * b > 9:
            t = 3 / math.hypot(a, b)
            m[k], m[k + 1] = t * a * d[k], t * b * d[k]
    out = [f"M{points[0][0]:.2f} {points[0][1]:.2f}"]
    for k in range(n - 1):
        (xa, ya), (xb, yb) = points[k], points[k + 1]
        out.append(f"C{xa + h / 3:.2f} {ya + m[k] * h / 3:.2f} {xb - h / 3:.2f} {yb - m[k + 1] * h / 3:.2f} {xb:.2f} {yb:.2f}")
    return "".join(out)


def gradient(uid, x0, x1):
    """The trace colour runs blue -> mint from the first sample shown to the last."""
    return (f'<linearGradient id="{uid}-sig" gradientUnits="userSpaceOnUse" x1="{x0:g}" y1="0" x2="{x1:g}" y2="0">'
            f'<stop offset="0" stop-color="{C["blue"]}"/><stop offset="1" stop-color="{C["mint"]}"/></linearGradient>')


def document(canvas: Canvas, title: str, desc: str, defs: str, radius: float) -> str:
    w, h, uid = canvas.w, canvas.h, canvas.uid
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-labelledby="{uid}-t {uid}-d">'
            f'<title id="{uid}-t">{escape(title)}</title><desc id="{uid}-d">{escape(desc)}</desc>'
            f'<defs><linearGradient id="{uid}-bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{C["bg0"]}"/>'
            f'<stop offset="1" stop-color="{C["bg1"]}"/></linearGradient>{defs}</defs>'
            f'<rect x=".75" y=".75" width="{w - 1.5:g}" height="{h - 1.5:g}" rx="{radius:g}" fill="url(#{uid}-bg)" stroke="{C["border"]}" stroke-width="1.5"/>')
    return head + "".join(canvas.parts) + "</svg>\n"


def best_breaks(face, text, size, max_width, lines, tracking=0.0):
    """Split text into `lines` lines that fit, preferring a break after punctuation, then balance."""
    words = text.split()
    if lines == 1:
        return [text] if face.width(text, size, tracking) <= max_width else None
    best = None
    for cuts in itertools.combinations(range(1, len(words)), lines - 1):
        bounds = (0, *cuts, len(words))
        rows = [" ".join(words[a:b]) for a, b in zip(bounds, bounds[1:])]
        widths = [face.width(r, size, tracking) for r in rows]
        if max(widths) > max_width:
            continue
        score = max(widths) - min(widths)                       # balance the rag
        score -= 60 * sum(r[-1] in ",;:" for r in rows[:-1])      # prefer breaking after punctuation
        score += 80 if len(rows[-1].split()) == 1 else 0          # avoid a one-word last line
        if best is None or score < best[0]:
            best = (score, rows)
    return best[1] if best else None


# --------------------------------------------------------------------------------- banners
W, H, M = 1280, 340, 72         # canvas and side margins
EYEBROW_SIZE, EYEBROW_TRACK = 15, 1.8
NAME_SIZE = 68
AFF_SIZE, AFF_LEAD = 18, 27
CAP = 0.714                     # Noto Sans cap height / em


def _hero_title(line):
    return f"{NAME}. {line} {AFFILIATIONS[0]}; {AFFILIATIONS[1][0].lower()}{AFFILIATIONS[1][1:]}."


def hero_horizon(faces, line=LINE, eyebrow=EYEBROW, samples=192):
    """The banner: a masthead over one long trace that runs margin to margin."""
    bold, regular = faces["bold"], faces["regular"]
    cv = Canvas(W, H, "hero")
    ye = 71                                      # eyebrow cap top at 60: the top margin
    yn = round(ye + 22 + CAP * NAME_SIZE)        # 142
    caps = {"case": True}
    cv.text(bold, eyebrow.upper(), M, ye, EYEBROW_SIZE, C["muted"], tracking=EYEBROW_TRACK, features=caps)
    cv.text(bold, NAME, M, yn, NAME_SIZE, C["ink"], tracking=-0.02 * NAME_SIZE)
    # positioning line: one line across the full measure, stepping down in size before wrapping
    for size in (28, 27, 26, 25, 24):
        rows = best_breaks(regular, line, size, W - 2 * M, 1, -0.005 * size)
        if rows:
            break
    else:                                         # very long: two balanced lines
        size = 26
        rows = best_breaks(regular, line, size, W - 2 * M, 2, -0.005 * size)
        if not rows:
            raise SystemExit(f"positioning line does not fit the banner: {line!r}")
    lead = round(size * 1.3)
    yl = yn + 46                                # 8 px between the name's descenders and the line's ascenders
    for i, row in enumerate(rows):
        cv.text(regular, row, M, yl + i * lead, size, C["ink"], tracking=-0.005 * size)
    for row, y in zip(AFFILIATIONS, (yn - AFF_LEAD, yn)):   # last baseline shared with the name
        cv.text(regular, row, W - M, y, AFF_SIZE, C["muted"], align="right")
    # the trace: zero line 60 px above the bottom edge (mirrors the top margin), peak = 1.0
    text_bottom = max(b[3] for k, _, b in cv.boxes if k == "text")
    amp, zero = 56.0, 280.0
    if zero - amp < text_bottom + 28:            # long lines that wrapped: keep 28 px of air
        zero = min(292.0, text_bottom + 28 + amp)
        amp = min(amp, (H - 22 - zero) / -min(SIGNAL[:samples]), zero - text_bottom - 28)
    head = 8
    points = trace_points(SIGNAL[:samples], M, W - M - head / 2, zero, amp)
    cv.trace(points, 2.0, head=head)
    desc = (f"The trace is his portrait as a single-pixel camera would record it: the first {samples} of 4,096 "
            "two-dimensional Walsh-Hadamard measurements after the DC term, in sequency order, drawn to linear scale; "
            "the amber square is the newest sample.")
    return document(cv, _hero_title(line), desc, gradient(cv.uid, M, W - M), 18), cv


# ----------------------------------------------------------------------------------- cards
CW, CH, PAD = 400, 150, 24
SPARK_SAMPLES, SPARK_W = 24, 72


def card(faces, spec):
    bold, regular = faces["bold"], faces["regular"]
    cv = Canvas(CW, CH, f"card-{spec['slug']}")
    cv.text(bold, spec["kind"].upper(), PAD, 31, 11, C["muted"], tracking=1.4, features={"case": True})
    cv.text(bold, spec["name"], PAD, 60, 22, C["ink"], tracking=-0.22)
    for row, y in zip(spec["text"], (85, 104)):
        if regular.width(row, 13.5) > CW - 2 * PAD:
            raise SystemExit(f"{spec['slug']}: description line too long: {row!r}")
        cv.text(regular, row, PAD, y, 13.5, C["muted"])
    cv.text(regular, spec["venue"], PAD, 129, 12.5, C["ink"])        # credibility first, in ink
    cv.text(regular, "·", cv.boxes[-1][2][2] + 6, 129, 12.5, C["muted"])
    cv.text(regular, spec["language"], cv.boxes[-1][2][2] + 6, 129, 12.5, C["muted"])  # equal ink gaps
    head = 4
    x1 = CW - PAD - head / 2
    zero = 129 - 0.536 * 12.5 / 2                # footer x-height centre
    points = trace_points(SIGNAL[:SPARK_SAMPLES], x1 - SPARK_W + head / 2, x1, zero, 9.0)
    cv.trace(points, 1.25, head=head)
    title = f"{spec['name']} ({spec['venue']}, {spec['language']}): {' '.join(spec['text'])}"
    desc = f"Sparkline: the first {SPARK_SAMPLES} single-pixel measurements of the author's portrait."
    return document(cv, title, desc, gradient(cv.uid, x1 - SPARK_W, x1 + head / 2), 12), cv


# ---------------------------------------------------------------------------------- checks
def luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def check_layout(name, cv, margin, clearance):
    """No text overlaps text; text keeps `clearance` px from the signal; ink stays inside `margin`."""
    problems = []
    texts = [(s, b) for k, s, b in cv.boxes if k == "text"]
    signal = [(s, b) for k, s, b in cv.boxes if k == "signal"]
    for (sa, a), (sb, b) in itertools.combinations(texts, 2):
        if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
            problems.append(f"text overlap: {sa!r} / {sb!r}")
    for s, a in texts:
        for g, b in signal:
            dx = max(b[0] - a[2], a[0] - b[2], 0)
            dy = max(b[1] - a[3], a[1] - b[3], 0)
            if math.hypot(dx, dy) < clearance:
                problems.append(f"{s!r} within {math.hypot(dx, dy):.1f} px of the {g}")
    for s, b in texts + signal:
        hang = 2.0  # optical hang may pass the margin by up to 2 px
        if b[0] < margin[0] - hang or b[2] > cv.w - margin[0] + 0.01 or b[1] < margin[1] or b[3] > cv.h - margin[1]:
            problems.append(f"{s!r} outside the safe area: {tuple(round(v, 1) for v in b)}")
    if problems:
        raise SystemExit(f"{name}: " + "; ".join(problems))


def check_file(path: Path, view):
    data = path.read_bytes()
    text = data.decode("utf-8")
    problems = [f"{len(data)} bytes > 150 KB"] if len(data) > 150 * 1024 else []
    problems += [] if f'viewBox="0 0 {view[0]} {view[1]}"' in text else ["wrong viewBox"]
    problems += ["CR line endings"] if b"\r" in data else []
    for pattern in (r"<text\b", r"<image\b", r"href=", r"@import", r"font-family", r"url\((?!#)", r"<script\b"):
        problems += [f"not self-contained ({pattern})"] if re.search(pattern, text) else []
    if problems:
        raise SystemExit(f"{path.name}: " + "; ".join(problems))
    return len(data)


def build(faces, line, eyebrow, out: Path | None):
    """Build every asset; write to `out` when given. Returns {file name: svg text}."""
    if len(eyebrow) > 50:
        raise SystemExit(f"eyebrow has {len(eyebrow)} characters (max 50)")
    files = {}
    svg, cv = hero_horizon(faces, line, eyebrow)
    check_layout("hero.svg", cv, (M, 24), clearance=24)
    files["hero.svg"] = svg
    for spec in CARDS:
        svg, cv = card(faces, spec)
        check_layout(spec["slug"], cv, (PAD, 14), clearance=8)
        files[f"card-{spec['slug']}.svg"] = svg
    if out:
        out.mkdir(parents=True, exist_ok=True)
        for name, svg in files.items():
            (out / name).write_text(svg, encoding="utf-8", newline="\n")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fonts", type=Path, required=True, help="folder with NotoSans-Regular/Bold.ttf")
    parser.add_argument("--line", default=LINE, help="positioning line (up to nine words)")
    parser.add_argument("--eyebrow", default=EYEBROW, help="eyebrow, at most 50 characters (set in capitals)")
    args = parser.parse_args()
    if len(args.line.split()) > 9:
        raise SystemExit("the positioning line has more than nine words")
    faces = {k: Face(args.fonts / f"NotoSans-{v}.ttf") for k, v in (("regular", "Regular"), ("bold", "Bold"))}
    for alternative in STRESS_LINES:             # layouts must hold for other lines too
        build(faces, alternative, args.eyebrow, None)
    build(faces, args.line, args.eyebrow, ASSETS)
    sizes = {"hero.svg": (W, H)}
    for spec in CARDS:
        sizes[f"card-{spec['slug']}.svg"] = (CW, CH)
    for name, view in sizes.items():
        print(f"{name}: {check_file(ASSETS / name, view):,} bytes")
    lightest = C["bg1"]                          # text is checked against the lighter gradient stop
    for role in ("ink", "muted"):
        ratio = contrast(C[role], lightest)
        if ratio < 4.5:
            raise SystemExit(f"{role} contrast {ratio:.2f}:1 is below 4.5:1")
        print(f"contrast {role} on {lightest}: {ratio:.2f}:1")
    print(f"stress-tested lines: {len(STRESS_LINES)}; all geometry checks passed")


if __name__ == "__main__":
    main()
