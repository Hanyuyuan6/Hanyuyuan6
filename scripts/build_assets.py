#!/usr/bin/env python3
"""Build the profile README's banner, project cards and link badges.

The banner is a synthetic concept illustration: sparse optical samples and one restrained
light trace lead into a hand-drawn brain volume with seven schematic tomography slices.
It is not a measurement, reconstruction, MRI, EEG recording or clinical result.

The card sparklines use four nonoverlapping 24-sample intervals of data/portrait-signal.json:
computed two-dimensional Walsh-Hadamard measurements of the author's public 64x64 portrait.
Each interval is independently linearly scaled and uses shape-preserving interpolation;
these are decorative identity motifs, not project measurements or performance. The gold
square marks the final scalar sample in each interval.

Motion is CSS @keyframes inside each SVG: GitHub shows README images in <img>, where CSS
animation runs and scripts never do. Each file's static content is the finished frame, so
renderers without animation, and readers who ask for reduced motion, see the complete
image. The banner's contour and slices remain fixed; a sparse sequence of small lights
passes along its trace without moving the anatomy. The card sparklines follow. Narrow images (two
cards across a phone, the banner on a phone) swap to a compact view by a width media query.

Text is shaped with HarfBuzz and outlined from Noto Sans (SIL OFL 1.1), so the SVGs embed
no fonts and render the same everywhere. One dark design serves both GitHub themes: README
files render in "markdown" mode, which splits a <picture> wrapped in a link.

    pip install fonttools==4.66.1 uharfbuzz==0.56.3
    python scripts/build_assets.py --fonts ../hanyuyuan6.github.io/fonts

Display copy comes from data/profile-display.json, a generated subset of the website's
public profile.json. Pass --profile ../hanyuyuan6.github.io/profile.json to refresh that
subset and README together; the snapshot's hash covers only its public fields. No local
source path or unpublished profile field is copied. Without --profile, the same shipped
snapshot reproduces the SVGs offline.

Every build re-checks its own geometry (no text touches the signal or other text, all ink
inside the margins), contrast, file size, self-containment and motion (each animation ends
on the static frame, reduced motion stops all of it), and stress-tests the banner with
longer positioning lines.
"""
from __future__ import annotations

import argparse
import hashlib
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
DISPLAY = ROOT / "data" / "profile-display.json"

# Brand palette: purple, gold and black. Type stays neutral. On the measured card traces,
# purple runs from earliest to latest sample; the gold square marks the latest sample.
C = {"bg0": "#0b0a10", "bg1": "#1a1426", "border": "#2e2540", "ink": "#f3efff", "muted": "#a9a1bd",
     "trace": "#8b5cf6", "trace_to": "#c4b5fd", "pixel": "#f5c33b"}

NAME = EYEBROW = LINE = ""  # all display copy is loaded from the generated public snapshot
AFFILIATIONS = ()
STRESS_LINES = (  # any positioning line of up to nine words must fit both banners
    "Teaching machines to see with a single pixel.",
    "Perception from single-pixel measurements, without ever forming images.",
    "Machine perception learned directly from compressive single-pixel optical measurements.",
    "Understanding scenes through compressive measurement-domain perception without reconstructing images.",
)
CARDS = [  # stable project titles; descriptions and publication venues come from the fact source
    {"slug": "stsf-tpls", "kind": "Paper + code", "name": "STSF-TPLS", "language": "PyTorch"},
    {"slug": "remote-gpu-trainer", "kind": "Open-source tool", "name": "remote-gpu-trainer", "venue": "Agent skill",
     "language": "Python"},
    {"slug": "shsi", "kind": "Paper + code", "name": "SHSI", "language": "MATLAB"},
    {"slug": "ldgi", "kind": "Paper + code", "name": "LDGI", "language": "MATLAB"},
]
BADGES = [  # README links, left to right; the website, the primary link, carries the gold pixel
    {"slug": "website", "label": "Website", "mark": "pixel"},
    {"slug": "scholar", "label": "Google Scholar", "mark": "trace"},
    {"slug": "orcid", "label": "ORCID", "mark": "trace"},
    {"slug": "linkedin", "label": "LinkedIn", "mark": "trace"},
    {"slug": "email", "label": "Email", "mark": "trace"},
]

# Optical margin: letters that touch the margin only with a point or a curve hang slightly
# past it so the column looks straight (fractions of the type size).
HANG = {"Y": 0.025, "A": 0.02, "V": 0.02, "W": 0.02, "T": 0.012, "O": 0.008, "C": 0.008, "G": 0.008, "S": 0.006}
CAP_HYPHEN_RAISE = 89  # font units: lifts the hyphen from x-height centre (268) to cap centre (357)
CAPS = {"case": True}


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


def num(v: float, digits: int = 2) -> str:
    return f"{v:.{digits}f}".rstrip("0").rstrip(".") or "0"


# ----------------------------------------------------------------------------------- signal
def trace_points(values, x0, x1, zero, amp):
    step = (x1 - x0) / (len(values) - 1)
    return [(x0 + i * step, zero - v * amp) for i, v in enumerate(values)]


def monotone_segments(points):
    """Fritsch-Carlson monotone cubic through every sample: no overshoot, no new extrema.
    Returns one cubic Bezier (p0, c1, c2, p1) per interval, rounded as written to the file."""
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
    r = lambda v: round(v, 2)  # noqa: E731  (the file holds two decimals; lengths are measured on that)
    segs = []
    for k in range(n - 1):
        (xa, ya), (xb, yb) = points[k], points[k + 1]
        segs.append(((r(xa), r(ya)), (r(xa + h / 3), r(ya + m[k] * h / 3)), (r(xb - h / 3), r(yb - m[k + 1] * h / 3)), (r(xb), r(yb))))
    return segs


def path_d(segs) -> str:
    out = [f"M{segs[0][0][0]:.2f} {segs[0][0][1]:.2f}"]
    for _, c1, c2, p1 in segs:
        out.append(f"C{c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {p1[0]:.2f} {p1[1]:.2f}")
    return "".join(out)


GL = [(-0.9739065285, 0.0666713443), (-0.8650633667, 0.1494513492), (-0.6794095683, 0.2190863625),
      (-0.4333953941, 0.2692667193), (-0.1488743390, 0.2955242247), (0.1488743390, 0.2955242247),
      (0.4333953941, 0.2692667193), (0.6794095683, 0.2190863625), (0.8650633667, 0.1494513492),
      (0.9739065285, 0.0666713443)]  # 10-point Gauss-Legendre nodes and weights


def bezier_length(p0, c1, c2, p1, pieces=8) -> float:
    """Arc length of one cubic, Gauss-Legendre on `pieces` sub-intervals (error far below 0.01 px)."""
    def speed(t):
        u = 1 - t
        dx = 3 * u * u * (c1[0] - p0[0]) + 6 * u * t * (c2[0] - c1[0]) + 3 * t * t * (p1[0] - c2[0])
        dy = 3 * u * u * (c1[1] - p0[1]) + 6 * u * t * (c2[1] - c1[1]) + 3 * t * t * (p1[1] - c2[1])
        return math.hypot(dx, dy)
    total = 0.0
    for i in range(pieces):
        a, b = i / pieces, (i + 1) / pieces
        total += sum(w * speed((a + b) / 2 + (b - a) / 2 * x) for x, w in GL) * (b - a) / 2
    return total


# ----------------------------------------------------------------------------------- motion
class Ease:
    """CSS cubic-bezier(x1, y1, x2, y2): time -> progress, and its inverse."""

    def __init__(self, x1, y1, x2, y2):
        self.p = (x1, y1, x2, y2)

    @staticmethod
    def _b(a, b, s):
        return 3 * a * (1 - s) ** 2 * s + 3 * b * (1 - s) * s * s + s ** 3

    def _solve(self, target, a, b):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if self._b(a, b, mid) < target else (lo, mid)
        return (lo + hi) / 2

    def time_at(self, progress):
        """The time fraction at which this easing reaches `progress`."""
        x1, y1, x2, y2 = self.p
        return self._b(x1, x2, self._solve(progress, y1, y2))


DRAW_EASE = Ease(0.3, 0.0, 0.2, 1.0)  # the sweep sets off gently and settles into the last sample
DRAW_DONE = 0.999                     # fraction of the draw at which the last sample is reached


class Motion:
    """CSS animation for one SVG. One-shot animations fill both ways and end on the element's static
    state; loops only fade light that is invisible when static."""

    def __init__(self, uid):
        self.uid = uid
        self.items = []  # dicts: cls, name, frames [(fraction, {prop: value})], duration, delay, timing, loop

    def add(self, cls, frames, duration, delay, timing="linear", loop=False):
        self.items.append({"cls": f"{self.uid}-{cls}", "name": f"{self.uid}-{cls}", "frames": frames,
                           "duration": duration, "delay": delay, "timing": timing, "loop": loop})
        return f"{self.uid}-{cls}"

    def draw(self, cls, trace, duration, delay):
        """Reveal a trace left to right, one sample per equal step of eased time: in arc length the steep
        early samples would take most of the sweep. The dash is one unit longer than the path; once the
        whole path is drawn (99.9%) the dash is dropped, so the last frame is the static path itself."""
        dash = trace["path_length"] + 1
        frames = []
        n = len(trace["cum"])
        for k, s in enumerate(trace["cum"]):
            t = 0.0 if k == 0 else DRAW_DONE if k == n - 1 else DRAW_DONE * DRAW_EASE.time_at(k / (n - 1))
            frames.append((t, {"stroke-dashoffset": dash - s}))
        frames[0][1]["stroke-dasharray"] = frames[-1][1]["stroke-dasharray"] = (dash, dash)
        frames.append((1.0, {"stroke-dashoffset": 0, "stroke-dasharray": "none"}))
        return self.add(cls, frames, duration, delay)

    def end(self):
        return max((i["delay"] + i["duration"] for i in self.items if not i["loop"]), default=0.0)

    def css(self) -> str:
        if not self.items:
            return ""
        rules, keyframes = [], []
        for i in self.items:
            loop = " infinite" if i["loop"] else ""
            rules.append(f".{i['cls']}{{animation:{i['name']} {num(i['duration'], 3)}s {i['timing']} "
                         f"{num(i['delay'], 3)}s{loop} both}}")
            steps, last = [], None
            for t, props in i["frames"]:
                pct = num(100 * t, 3)
                if pct == last:
                    continue
                last = pct
                body = ";".join(f"{k}:{' '.join(num(x, 1) for x in v) if isinstance(v, tuple) else v if isinstance(v, str) else num(v, 3)}"
                                for k, v in props.items())
                steps.append(f"{pct}%{{{body}}}")
            keyframes.append(f"@keyframes {i['name']}{{{''.join(steps)}}}")
        quiet = ",".join(f".{i['cls']}" for i in self.items)
        return "".join(rules) + "".join(keyframes) + f"@media (prefers-reduced-motion:reduce){{{quiet}{{animation:none}}}}"


# ----------------------------------------------------------------------------------- canvas
class Canvas:
    """Collects SVG elements plus the ink box of every text run and graphic, for the checks."""

    def __init__(self, width, height, uid, compact_below=None):
        self.w, self.h, self.uid = width, height, uid  # uid prefixes ids and classes: SVGs may share a page
        self.parts: list[str] = []
        self.defs: list[str] = []
        self.boxes: list[tuple[str, str, tuple[float, float, float, float]]] = []  # full view: (kind, label, box)
        self.compact_parts: list[str] = []
        self.compact_boxes: list[tuple[str, str, tuple[float, float, float, float]]] = []  # compact view's text
        self.compact_below = compact_below  # rendered width (CSS px) at or below which the compact view shows
        self.static: dict[str, dict] = {}  # class -> static state of the animated element, for the checks
        self.motion = Motion(uid)

    def text(self, face, s, x, y, size, fill, *, tracking=0.0, features=None, align="left", view="full"):
        """Place a run so its ink (not its advance box) starts at x, or ends at x when align='right'.
        view: 'full' (the static layout, hidden when the image is narrow) or 'compact' (narrow images only)."""
        left, _, right, _ = face.ink(s, 0, 0, size, tracking, features)
        x0 = x - left - min(HANG.get(s[0], 0) * size, 2.0) if align == "left" else x - right  # hang <= 2 px
        d = face.path(s, x0, y, size, tracking, features)
        box = face.ink(s, x0, y, size, tracking, features)
        if view == "compact":
            self.compact_parts.append(f'<path fill="{fill}" d="{d}"/>')
            self.compact_boxes.append(("text", s, box))
        else:
            cls = f' class="{self.uid}-full"' if self.compact_below else ""
            self.parts.append(f'<path{cls} fill="{fill}" d="{d}"/>')
            self.boxes.append(("text", s, box))
        return box

    def views(self):
        """(name, boxes) per view; the graphics belong to both."""
        graphics = [b for b in self.boxes if b[0] != "text"]
        out = [("full", self.boxes)]
        if self.compact_parts:
            out.append(("compact", self.compact_boxes + graphics))
        return out

    def trace(self, points, width, head=0.0, halo=0.0):
        """The signal, its pixel (gold square on the newest sample) and the pixel's halo (drawn first,
        under the trace: invisible when static, it carries the idle breath)."""
        segs = monotone_segments(points)
        lengths = [bezier_length(*s) for s in segs]
        true_length = sum(lengths)
        path_length = math.ceil(true_length)  # pathLength ~ true length: identical dashes whether or not honoured
        scale = path_length / true_length
        cum = [0.0] + list(itertools.accumulate(v * scale for v in lengths))
        cum[-1] = float(path_length)  # exact: the drawn frame must cover the whole path
        hx, hy = segs[-1][3]
        if halo:
            self.defs.append(f'<radialGradient id="{self.uid}-halo"><stop offset="0" stop-color="{C["pixel"]}" stop-opacity=".6"/>'
                             f'<stop offset=".38" stop-color="{C["pixel"]}" stop-opacity=".2"/>'
                             f'<stop offset="1" stop-color="{C["pixel"]}" stop-opacity="0"/></radialGradient>')
            self.parts.append(f'<circle class="{self.uid}-halo" cx="{hx:g}" cy="{hy:g}" r="{halo:g}" fill="url(#{self.uid}-halo)" opacity="0"/>')
            self.boxes.append(("glow", "halo", (hx - halo, hy - halo, hx + halo, hy + halo)))
            self.static[f"{self.uid}-halo"] = {"opacity": 0.0}
        self.parts.append(f'<path class="{self.uid}-trace" d="{path_d(segs)}" pathLength="{path_length}" fill="none" '
                          f'stroke="url(#{self.uid}-sig)" stroke-width="{width:g}" stroke-linejoin="round" stroke-linecap="butt"/>')
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        half = width / 2  # monotone cubic: the curve never leaves the samples' range
        self.boxes.append(("signal", "trace", (min(xs), min(ys) - half, max(xs), max(ys) + half)))
        self.static[f"{self.uid}-trace"] = {"path_length": path_length}
        if head:
            self.parts.append(f'<rect class="{self.uid}-pixel" x="{hx - head / 2:.2f}" y="{hy - head / 2:.2f}" width="{head:g}" height="{head:g}" fill="{C["pixel"]}"/>')
            self.boxes.append(("signal", "pixel", (hx - head / 2, hy - head / 2, hx + head / 2, hy + head / 2)))
            self.static[f"{self.uid}-pixel"] = {"opacity": 1.0}
        return {"path_length": path_length, "cum": cum}


def gradient(uid, x0, x1):
    """The trace colour runs deep -> light purple from the first sample shown to the last."""
    return (f'<linearGradient id="{uid}-sig" gradientUnits="userSpaceOnUse" x1="{x0:g}" y1="0" x2="{x1:g}" y2="0">'
            f'<stop offset="0" stop-color="{C["trace"]}"/><stop offset="1" stop-color="{C["trace_to"]}"/></linearGradient>')


def document(canvas: Canvas, title: str, desc: str, radius: float, inset: float = 0.0, stroke: float = 1.0) -> str:
    """`inset`: transparent margin around the tile (badges keep their spacing inside the image). `stroke`: the
    tile's border, chosen so every tile's edge renders near 0.9 px at a 740 px README column. The compact
    view is a group hidden by attribute: renderers without CSS, and librsvg, show the full layout."""
    w, h, uid = canvas.w, canvas.h, canvas.uid
    css = canvas.motion.css()
    if canvas.compact_parts:
        css += (f"@media (max-width:{canvas.compact_below}px){{.{uid}-full{{display:none}}"
                f".{uid}-compact{{display:inline}}}}")
    style = f"<style>{css}</style>" if css else ""
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" width="{w:g}" height="{h:g}" role="img" aria-labelledby="{uid}-t {uid}-d">'
            f'<title id="{uid}-t">{escape(title)}</title><desc id="{uid}-d">{escape(desc)}</desc>'
            f'<defs>{style}<linearGradient id="{uid}-bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{C["bg0"]}"/>'
            f'<stop offset="1" stop-color="{C["bg1"]}"/></linearGradient>{"".join(canvas.defs)}</defs>'
            f'<rect x="{inset + stroke / 2:g}" y="{stroke / 2:g}" width="{w - 2 * inset - stroke:g}" height="{h - stroke:g}" rx="{radius:g}" fill="url(#{uid}-bg)" stroke="{C["border"]}" stroke-width="{stroke:g}"/>')
    compact = f'<g class="{uid}-compact" display="none">{"".join(canvas.compact_parts)}</g>' if canvas.compact_parts else ""
    return head + "".join(canvas.parts) + compact + "</svg>\n"


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


def public_display(profile: dict) -> dict:
    """Copy only public display fields; the website's profile.json is the sole authoring source."""
    narrative = profile['narrative']
    long_term = next(s for s in narrative['bio'].split('. ') if s.startswith('My long-term aim'))
    publications = {p['id']: p for p in profile['publications']}
    return {
        'person': {key: profile['person'][key] for key in ('name', 'position', 'institution')},
        'narrative': {**{key: narrative[key] for key in ('field', 'hero', 'short_bio', 'current_summary', 'welcome')},
                      'long_term': long_term.rstrip('.') + '.'},
        'projects': [{**{key: p[key] for key in ('id', 'summary', 'context', 'code_url')},
                      'venue': publications[p['publication_id']]['venue'],
                      'year': publications[p['publication_id']]['year']}
                     for p in profile['projects'] if p['id'] in ('lift', 'shsi', 'loop')],
        'tool': next({key: p[key] for key in ('name', 'description', 'url')}
                     for p in profile['software'] if p['name'] == 'remote-gpu-trainer'),
    }


def use_display(data: dict):
    global NAME, EYEBROW, LINE, AFFILIATIONS
    NAME = data['person']['name']
    EYEBROW, LINE = data['narrative']['field'], data['narrative']['hero']
    AFFILIATIONS = (f"{data['person']['position']}, {data['person']['institution']}",)
    projects = {p['id']: p for p in data['projects']}
    for spec in CARDS:
        if spec['slug'] == 'remote-gpu-trainer':
            spec['summary'] = data['tool']['description']
            spec['context'] = ''
        else:
            p = projects[{'stsf-tpls': 'lift', 'shsi': 'shsi', 'ldgi': 'loop'}[spec['slug']]]
            spec['summary'], spec['context'] = p['summary'], p['context']
            spec['venue'] = f"{p['venue']} {p['year']}"


def sync_readme(data: dict):
    """Retain every existing link and project title; replace only source-derived display text."""
    path = ROOT / 'README.md'
    text = path.read_text(encoding='utf-8')
    person = data['person']
    hero_title = (f"{person['name']}. {data['narrative']['field']}. "
                  f"{person['position']}, {person['institution']}.")
    text = re.sub(r'(<img src="assets/(hero\.svg|hero-monolith\.webp)"[^>]* alt=")[^"]*',
                  lambda m: m.group(1) + escape(_hero_title(data['narrative']['hero']) if m.group(2) == 'hero.svg' else hero_title,
                                               {'"': '&quot;'}), text, count=1)
    n = data['narrative']
    biography = (n['short_bio'] + '\n\n'
                 f"- **Now:** {n['current_summary']}\n"
                 f"- **Long term:** {n['long_term'].removeprefix('My long-term aim is to ')}\n"
                 f"\n{n['welcome']}")
    start, end = text.index('\nI study '), text.index('\n\n### Featured work')
    text = text[:start] + '\n' + biography + text[end:]
    for spec in CARDS:
        note = f" Context: {spec['context']}." if spec.get('context') else ''
        alt = f"{spec['name']} ({spec['venue']}, {spec['language']}): {spec['summary']}{note}"
        pattern = rf'(<img src="assets/card-{re.escape(spec["slug"])}(?:-(?:g4|monolith))?\.(?:svg|webp)"[^>]* alt=")[^"]*'
        text = re.sub(pattern, lambda m: m.group(1) + escape(alt, {'"': '&quot;'}), text, count=1)
    path.write_text(text, encoding='utf-8', newline='\n')


# --------------------------------------------------------------------------------- banner
W, H, M = 1280, 340, 64         # canvas and side margins
EYEBROW_SIZE, EYEBROW_TRACK = 15.5, 1.6
NAME_SIZE = 76
AFF_SIZE, AFF_LEAD = 22, 30    # ~13 px at 740
CAP = 0.714                     # Noto Sans cap height / em
HERO_COMPACT = (600, 100, 50)   # phone: readable identity lockup, the same complete brain volume
HERO_DRAW = (0.25, 2.8)
HERO_LAND = 0.35
HERO_BREATH = 9.6

# A drawn lateral brain outline, deliberately schematic. No anatomy dataset is used.
# Seven cross-section curves and two offset contours suggest a volume; cortical grooves
# identify the brain without the node-to-node links of a neural-network diagram.
BRAIN_OUTLINE = ("M-131 -4C-144 -21 -132 -47 -114 -49C-113 -69 -92 -85 -71 -82"
                 "C-58 -103 -30 -110 -8 -101C8 -113 34 -107 49 -94"
                 "C74 -96 94 -79 99 -61C121 -55 133 -34 129 -13"
                 "C144 1 141 24 125 36C128 56 110 71 92 72"
                 "C84 91 57 98 37 87C17 95 -6 93 -22 85"
                 "C-45 94 -69 85 -80 72C-107 71 -126 55 -124 36"
                 "C-143 26 -144 7 -131 -4Z")
BRAIN_GROOVES = (
    "M-111 -27C-94 -38 -79 -32 -72 -15C-65 1 -69 16 -56 25",
    "M-92 -57C-81 -47 -55 -56 -50 -38C-45 -21 -57 -9 -43 1C-31 9 -19 1 -10 12",
    "M-54 -83C-37 -69 -47 -53 -28 -47C-11 -42 1 -49 9 -33",
    "M-6 -88C-19 -68 8 -63 23 -67C42 -71 53 -57 49 -40",
    "M60 -74C52 -55 67 -40 85 -40C103 -40 108 -21 97 -9",
    "M-115 14C-96 3 -86 21 -91 35C-96 51 -75 60 -59 53C-39 45 -23 51 -21 71",
    "M-38 23C-20 17 -18 33 -1 36C18 40 31 28 44 38C57 49 47 66 62 75",
    "M7 -10C25 -20 29 -3 43 1C60 6 74 -2 79 14C86 34 109 24 120 15",
)


def brain_concept(cv: Canvas):
    """Keep all conceptual graphics in a group, separate from outlined text and measured card traces."""
    uid = cv.uid
    cv.defs.extend((
        f'<linearGradient id="{uid}-cortex" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#b69ad6"/>'
        '<stop offset=".68" stop-color="#8e6cad"/><stop offset="1" stop-color="#d8b779"/></linearGradient>',
        f'<radialGradient id="{uid}-light"><stop stop-color="#e2bd6c" stop-opacity=".38"/>'
        '<stop offset=".35" stop-color="#e2bd6c" stop-opacity=".13"/>'
        '<stop offset="1" stop-color="#e2bd6c" stop-opacity="0"/></radialGradient>',
        f'<clipPath id="{uid}-brain-clip"><path d="{BRAIN_OUTLINE}"/></clipPath>',
    ))
    out = [f'<g id="{uid}-concept" data-illustration="synthetic-optical-brain">']
    # The source is a fabricated single-peaked arrival-time envelope, rather than an EEG-like oscillation.
    arrival = []
    for i in range(65):
        t = i / 9
        v = (t ** 2.2 * math.exp(-t)) / (2.2 ** 2.2 * math.exp(-2.2))
        arrival.append(f'{"M" if i == 0 else "L"}{num(718 + i * 1.55)} {num(263 - v * 21)}')
    out.append(f'<path class="{uid}-optical-input" d="{"".join(arrival)}" fill="none" '
               'stroke="#9677b2" stroke-opacity=".48" stroke-width="1.3"/>')
    # Two offset shell contours make the depth legible at thumbnail scale.
    out.append('<g transform="translate(1028 156) scale(1.04)">')
    for depth in (2, 1):
        out.append(f'<path class="{uid}-depth" d="{BRAIN_OUTLINE}" '
                   f'transform="translate({-depth * 15} {depth * 8})" fill="none" '
                   f'stroke="#9677b2" stroke-opacity="{num(.13 + (2 - depth) * .07)}" stroke-width=".8"/>')
    out.append(f'<path class="{uid}-brain-outline" d="{BRAIN_OUTLINE}" '
               f'fill="#171121" fill-opacity=".75" stroke="url(#{uid}-cortex)" stroke-width="1.6"/>')
    out.append(f'<g class="{uid}-slices" opacity="1" clip-path="url(#{uid}-brain-clip)">')
    for i in range(7):
        y = -79 + i * 26
        d = (f'M-151 {y - 12}C-71 {y + 31} 42 {y + 30} 151 {y - 1}'
             f'M-151 {y - 9}C-71 {y + 34} 42 {y + 33} 151 {y + 2}')
        out.append(f'<path class="{uid}-slice" data-slice="{i + 1}" d="{d}" fill="none" '
                   f'stroke="{"#cead78" if i == 3 else "#aa85c6"}" '
                   f'stroke-opacity="{.46 if i == 3 else .22}" stroke-width="{1 if i == 3 else .65}"/>')
    out.append('</g>')
    for d in BRAIN_GROOVES:
        out.append(f'<path class="{uid}-cortical-groove" d="{d}" fill="none" '
                   'stroke="#b293c9" stroke-opacity=".50" stroke-width="1.0" stroke-linecap="round"/>')
    # The cerebellum and a short brain stem complete the silhouette without an anatomical-data claim.
    out.append(f'<path class="{uid}-cerebellum" d="M51 81C71 67 95 72 103 89C109 105 88 117 68 110C56 108 46 94 51 81Z" '
               'fill="#191321" stroke="#9776ad" stroke-opacity=".55" stroke-width="1.0"/>')
    for i in range(4):
        y = 84 + i * 6
        out.append(f'<path d="M56 {y}Q78 {y - 8} 99 {y + 1}" fill="none" stroke="#b192c6" stroke-opacity=".30" stroke-width=".7"/>')
    out.append('<path d="M36 88C43 99 41 114 33 128L18 122C27 109 24 99 20 93" '
               'fill="none" stroke="#b297c5" stroke-opacity=".52" stroke-width="1.2"/>')
    # Samples are fixed in space. Their uneven density provides depth, without network edges.
    out.append(f'<g class="{uid}-samples" opacity="1" clip-path="url(#{uid}-brain-clip)">')
    for row in range(6):
        for col in range(10):
            x = -117 + col * 25 + math.sin(row * 1.5 + col * .7) * 4
            y = -73 + row * 29 + math.cos(col * 1.3 + row) * 5
            gold = (row * 10 + col) % 13 == 0
            out.append(f'<circle class="{uid}-sample" cx="{num(x)}" cy="{num(y)}" '
                       f'r="{1.65 if gold else 1.0}" fill="{"#e2bd6c" if gold else "#b397d0"}" '
                       f'opacity="{.85 if gold else .46}"/>')
    out.append('</g></g>')
    outside = ((742, 102), (789, 76), (831, 115), (755, 169), (811, 181), (850, 69),
               (735, 223), (784, 287), (846, 267), (1168, 71), (1204, 214), (1135, 294))
    for i, (x, y) in enumerate(outside):
        out.append(f'<circle class="{uid}-constellation" cx="{x}" cy="{y}" r="{1.8 if i % 3 else 2.5}" '
                   f'fill="{"#d2af74" if i % 3 == 0 else "#a88ac0"}" opacity="{.55 if i % 3 else .75}"/>')
    # G8: one fine Bézier trace. The constant base survives static/reduced-motion rendering.
    segs = (((727, 258), (801, 270), (792, 91), (890, 94)),
            ((890, 94), (987, 96), (1070, 222), (1181, 156)))
    d = path_d(segs)
    length = math.ceil(sum(bezier_length(*s) for s in segs))
    out.append(f'<path d="{d}" fill="none" stroke="#8e709d" stroke-opacity=".25" stroke-width=".85"/>')
    out.append(f'<path class="{uid}-trace" d="{d}" pathLength="{length}" fill="none" '
               'stroke="#e2bd6c" stroke-opacity=".58" stroke-width="1.1" stroke-linecap="round"/>')
    out.append(f'<circle class="{uid}-halo" cx="1181" cy="156" r="14" fill="url(#{uid}-light)" opacity="0"/>')
    out.append(f'<circle class="{uid}-pixel" cx="1181" cy="156" r="2.2" fill="#e4c586" opacity="1"/>')
    delay, duration = HERO_DRAW
    loop_start = delay + duration + HERO_LAND
    cv.motion.add('halo', [(0, {'opacity': 0}), (.83, {'opacity': .8}), (1, {'opacity': 0})],
                  HERO_BREATH, loop_start, timing='ease-in-out', loop=True)
    cv.static[f'{uid}-halo'] = {'opacity': 0.0}
    cv.motion.add('trace', [(0, {'stroke-dashoffset': length + 1, 'stroke-dasharray': (length + 1, length + 1)}),
                            (.999, {'stroke-dashoffset': 0, 'stroke-dasharray': (length + 1, length + 1)}),
                            (1, {'stroke-dashoffset': 0, 'stroke-dasharray': 'none'})], duration, delay)
    cv.static[f'{uid}-trace'] = {'path_length': length}
    cv.motion.add('pixel', [(0, {'opacity': 0}), (1, {'opacity': 1})], HERO_LAND, delay + duration, timing='ease-in-out')
    cv.static[f'{uid}-pixel'] = {'opacity': 1.0}
    for key, start in (('slices', .2), ('samples', .45)):
        cv.motion.add(key, [(0, {'opacity': 0}), (1, {'opacity': 1})], 1.8, start, timing='ease-in-out')
        cv.static[f'{uid}-{key}'] = {'opacity': 1.0}
    # An apparent travelling light uses small cross-fades, not CSS motion paths or scripts.
    for i in range(12):
        t = (i + 1) / 13
        s = segs[0] if t < .5 else segs[1]
        u = t * 2 if t < .5 else (t - .5) * 2
        point = tuple((1 - u) ** 3 * s[0][a] + 3 * (1 - u) ** 2 * u * s[1][a]
                      + 3 * (1 - u) * u ** 2 * s[2][a] + u ** 3 * s[3][a] for a in (0, 1))
        cls = f'photon-{i}'
        peak = .08 + i * .062
        out.append(f'<g class="{uid}-{cls}" opacity="0"><circle cx="{num(point[0])}" cy="{num(point[1])}" '
                   f'r="10" fill="url(#{uid}-light)"/><circle cx="{num(point[0])}" cy="{num(point[1])}" '
                   'r="2.1" fill="#f0dca6"/></g>')
        cv.motion.add(cls, [(0, {'opacity': 0}), (peak - .055, {'opacity': 0}),
                            (peak, {'opacity': .95}), (peak + .055, {'opacity': 0}), (1, {'opacity': 0})],
                      HERO_BREATH, loop_start, timing='ease-in-out', loop=True)
        cv.static[f'{uid}-{cls}'] = {'opacity': 0.0}
    out.append('</g>')
    cv.parts.append(''.join(out))
    cv.boxes.append(('signal', 'synthetic optical-signal brain volume', (711, 37, 1210, 297)))


def _hero_title(line):
    rest = "".join(f"; {a[0].lower()}{a[1:]}" for a in AFFILIATIONS[1:])
    return f"{NAME}. {line} {AFFILIATIONS[0]}{rest}."


def hero_horizon(faces, line=LINE, eyebrow=EYEBROW):
    """An identity lockup beside a sparse, layered brain volume; content never depends on motion."""
    bold, regular = faces["bold"], faces["regular"]
    cv = Canvas(W, H, "hero", compact_below=HERO_COMPACT[0])
    ye, yn = 69, 146
    cv.text(bold, eyebrow.upper(), M, ye, EYEBROW_SIZE, C["muted"], tracking=EYEBROW_TRACK, features=CAPS)
    cv.text(bold, NAME, M, yn, NAME_SIZE, C["ink"], tracking=-0.02 * NAME_SIZE)
    # Two lines preserve breathing room around the three-dimensional drawing.
    for size in (27, 26, 25, 24, 23, 22, 21, 20):
        rows = best_breaks(regular, line, size, 610, 2, -0.005 * size)
        if rows:
            break
    else:                                         # very long: two balanced lines
        raise SystemExit(f"positioning line does not fit the banner: {line!r}")
    lead = round(size * 1.3)
    yl = 204
    for i, row in enumerate(rows):
        cv.text(regular, row, M, yl + i * lead, size, C["ink"], tracking=-0.005 * size)
    for i, row in enumerate(AFFILIATIONS):
        cv.text(regular, row, M, 291 + i * AFF_LEAD, AFF_SIZE, C["muted"])
    # compact view: on a phone the banner is ~360 px wide and its small type would render at ~5 px, so the
    # name and the affiliation, larger, stand over the trace as one left-aligned lockup
    _, big, small = HERO_COMPACT
    yb = 132
    cv.text(bold, NAME, M, yb, big, C["ink"], tracking=-0.02 * big, view="compact")
    identity = AFFILIATIONS[0].split(', ', 1)
    for i, row in enumerate(identity):
        cv.text(regular, row, M, 203 + i * 63, small if i == 0 else 46, C["muted"], view="compact")
    brain_concept(cv)
    desc = ("Synthetic concept illustration: sparse optical samples and a fine luminous trace lead into a "
            "schematic brain volume with seven tomography slices. Inspired by time-domain diffuse optical "
            "tomography for 3D brain imaging. The signals and anatomy are drawn, not measured data or a clinical reconstruction.")
    return document(cv, _hero_title(line), desc, 8, stroke=1.5), cv


# ----------------------------------------------------------------------------------- cards
CW, CH, PAD = 400, 150, 24
SPARK_SAMPLES, SPARK_W = 24, 72
CARD_COMPACT = (300, 36, 24)    # at or below 300 px wide (two cards across a phone): name and venue, larger
CARD_DRAW = (2.1, 0.12, 1.0)    # first delay (s), stagger per card in README order, duration


def card(faces, spec, index=0):
    bold, regular = faces["bold"], faces["regular"]
    cv = Canvas(CW, CH, f"card-{spec['slug']}", compact_below=CARD_COMPACT[0])
    ks, yk = 11, 31                              # label cap top on the 23 px top margin
    cv.text(bold, spec["kind"].upper(), PAD, yk, ks, C["muted"], tracking=1.4, features=CAPS)
    cv.text(bold, spec["name"], PAD, 59.5, 22.5, C["ink"], tracking=-0.22)
    summary = spec['summary']
    rows, size = None, 13.5
    for count in (2, 3):
        for size in (13.5, 13, 12.5):
            rows = best_breaks(regular, summary, size, CW - 2 * PAD, count)
            if rows:
                break
        if rows:
            break
    if not rows:
        raise SystemExit(f"{spec['slug']}: description does not fit: {summary!r}")
    for i, row in enumerate(rows):
        cv.text(regular, row, PAD, 81 + i * 16, size, C['muted'])
    foot, fs = 132.5 if len(rows) == 3 else 127, 13
    cv.text(regular, spec["venue"], PAD, foot, fs, C["ink"])          # credibility first, in ink
    cv.text(regular, "·", cv.boxes[-1][2][2] + 6, foot, fs, C["muted"])
    cv.text(regular, spec["language"], cv.boxes[-1][2][2] + 6, foot, fs, C["muted"])  # equal ink gaps
    # compact view: two cards across a phone are ~170 px wide; name and venue grow, the rest waits on desktop
    _, big, venue = CARD_COMPACT
    for text, face, size, y, colour, track in ((spec["name"], bold, big, 80, C["ink"], -0.01 * big),
                                               (spec["venue"], regular, venue, 121, C["ink"], 0.0)):
        if face.width(text, size, track) > CW - 2 * PAD:
            raise SystemExit(f"{spec['slug']}: compact line too long: {text!r}")
        cv.text(face, text, PAD, y, size, colour, tracking=track, view="compact")
    head = 4
    x1 = CW - PAD - head / 2
    zero = yk - CAP * ks / 2                     # the sparkline signs the card in its label row
    start = index * SPARK_SAMPLES
    values = SIGNAL[start:start + SPARK_SAMPLES]
    points = trace_points(values, x1 - SPARK_W + head / 2, x1, zero, 9.0 / max(abs(v) for v in values))
    trace = cv.trace(points, 1.25, head=head)
    first, stagger, duration = CARD_DRAW
    delay = first + stagger * index
    cv.motion.draw("trace", trace, duration, delay)
    cv.motion.add("pixel", [(0, {"opacity": 0}), (1, {"opacity": 1})], 0.3, delay + duration - 0.05,
                  timing="cubic-bezier(.2,0,0,1)")
    title = f"{spec['name']} ({spec['venue']}, {spec['language']}): {summary}"
    desc = (f"Portrait-derived decorative motif: computed Walsh-Hadamard samples {start + 1} through "
            f"{start + SPARK_SAMPLES} of the author's public portrait. Each interval is independently linearly "
            "scaled; these are not project measurements or performance.")
    if spec.get('context'):
        desc += f" Research context: {spec['context']}."
    cv.defs.append(gradient(cv.uid, x1 - SPARK_W, x1 + head / 2))
    return document(cv, title, desc, 12), cv


# ---------------------------------------------------------------------------------- badges
BH, B_INSET = 28, 3             # chip height; transparent margin left and right (spacing between chips)
B_SIZE, B_TRACK = 11, 1.2       # label: bold capitals, tracked like the card labels
B_MARK = 6                      # the square: a pixel


def badge(faces, spec):
    bold = faces["bold"]
    label = spec["label"].upper()
    lw = bold.width(label, B_SIZE, B_TRACK, CAPS)
    pad_l, gap, pad_r = 10, 7, 11
    width = round(B_INSET + pad_l + B_MARK + gap + lw + pad_r + B_INSET)
    cv = Canvas(width, BH, f"badge-{spec['slug']}")
    mid = BH / 2
    mx = B_INSET + pad_l
    cv.parts.append(f'<rect x="{mx:g}" y="{mid - B_MARK / 2:g}" width="{B_MARK}" height="{B_MARK}" fill="{C[spec["mark"]]}"/>')
    cv.boxes.append(("signal", "mark", (mx, mid - B_MARK / 2, mx + B_MARK, mid + B_MARK / 2)))
    cv.text(bold, label, mx + B_MARK + gap, mid + CAP * B_SIZE / 2, B_SIZE, C["ink"], tracking=B_TRACK, features=CAPS)
    return document(cv, spec["label"], f"Link: {spec['label']}.", 6, inset=B_INSET), cv


# ---------------------------------------------------------------------------------- checks
def luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def check_layout(name, cv, margin, clearance):
    """In every view: no text overlaps text; text keeps `clearance` px from the signal and the halo; ink
    stays inside `margin` (x, y); the halo, light without edges, may run to the tile's edge, not past it."""
    problems = []
    for view, boxes in cv.views():
        texts = [(s, b) for k, s, b in boxes if k == "text"]
        signal = [(s, b) for k, s, b in boxes if k in ("signal", "glow")]
        for (sa, a), (sb, b) in itertools.combinations(texts, 2):
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                problems.append(f"{view}: text overlap: {sa!r} / {sb!r}")
        for s, a in texts:
            for g, b in signal:
                dx = max(b[0] - a[2], a[0] - b[2], 0)
                dy = max(b[1] - a[3], a[1] - b[3], 0)
                if math.hypot(dx, dy) < clearance:
                    problems.append(f"{view}: {s!r} within {math.hypot(dx, dy):.1f} px of the {g}")
        for s, b in texts + [(g, b) for k, g, b in boxes if k == "signal"]:
            hang = 2.0  # optical hang may pass the margin by up to 2 px
            if b[0] < margin[0] - hang or b[2] > cv.w - margin[0] + 0.01 or b[1] < margin[1] or b[3] > cv.h - margin[1]:
                problems.append(f"{view}: {s!r} outside the safe area: {tuple(round(v, 1) for v in b)}")
        for g, b in [(g, b) for k, g, b in boxes if k == "glow"]:
            if b[0] < 0 or b[1] < 0 or b[2] > cv.w or b[3] > cv.h:
                problems.append(f"{view}: {g} leaves the tile: {tuple(round(v, 1) for v in b)}")
    if problems:
        raise SystemExit(f"{name}: " + "; ".join(problems))


def check_motion(name, cv):
    """Each one-shot animation ends on the element's static state, the loop breathes only light that is
    invisible when static, everything settles within 4.5 s and reduced motion stops every animation."""
    problems = []
    for i in cv.motion.items:
        static = cv.static.get(i["cls"])
        last = i["frames"][-1][1]
        if static is None:
            problems.append(f"{i['cls']}: animates an element the checks do not know")
            continue
        if i["loop"]:
            if static.get("opacity") != 0 or set().union(*(f.keys() for _, f in i["frames"])) != {"opacity"}:
                problems.append(f"{i['cls']}: only light that is invisible when static may loop, by opacity")
            if i["duration"] < 4 or i["frames"][0][1]["opacity"] != 0 or last["opacity"] != 0:
                problems.append(f"{i['cls']}: the breath must last 4 s or more and start and end dark")
        elif "opacity" in last and last["opacity"] != static.get("opacity"):
            problems.append(f"{i['cls']}: ends at opacity {last['opacity']}, static {static.get('opacity')}")
        elif "stroke-dashoffset" in last:
            drawn = i["frames"][-2][1]  # the whole path shows before the dash is dropped
            dash = drawn.get("stroke-dasharray", (0, 0))[0]
            if last.get("stroke-dasharray") != "none" or last["stroke-dashoffset"] != 0 or \
                    dash < static["path_length"] or drawn["stroke-dashoffset"] > dash - static["path_length"]:
                problems.append(f"{i['cls']}: does not end on the static, fully drawn path")
        times = [t for t, _ in i["frames"]]
        if times[0] != 0 or times[-1] != 1 or any(b < a for a, b in zip(times, times[1:])):
            problems.append(f"{i['cls']}: keyframes out of order")
    if cv.motion.end() > 4.5:
        problems.append(f"motion settles at {cv.motion.end():.2f} s (> 4.5 s)")
    if problems:
        raise SystemExit(f"{name}: " + "; ".join(problems))


ALLOWED_CSS = re.compile(r"(?:\.[a-z0-9-]+\{animation:[a-z0-9-]+ [\d.]+s (?:linear|ease-in-out|cubic-bezier\([\d.,]+\)) "
                         r"[\d.]+s(?: infinite)? both\})*"
                         r"(?:@keyframes [a-z0-9-]+\{(?:[\d.]+%\{(?:(?:opacity|stroke-dashoffset|stroke-dasharray):(?:[\d. ]+|none);?)+\})+\})*"
                         r"(?:@media \(prefers-reduced-motion:reduce\)\{(?:\.[a-z0-9-]+,?)+\{animation:none\}\})?"
                         r"(?:@media \(max-width:\d+px\)\{\.[a-z0-9-]+\{display:none\}\.[a-z0-9-]+\{display:inline\}\})?")


def check_file(path: Path, view):
    data = path.read_bytes()
    text = data.decode("utf-8")
    problems = [f"{len(data)} bytes > 150 KB"] if len(data) > 150 * 1024 else []
    problems += [] if f'viewBox="0 0 {view[0]} {view[1]}"' in text else ["wrong viewBox"]
    problems += ["CR line endings"] if b"\r" in data else []
    for pattern in (r"<text\b", r"<image\b", r"href=", r"@import", r"@font-face", r"font-family", r"url\((?!#)",
                    r"<script\b", r"<animate", r"<set\b", r"<foreignObject"):
        problems += [f"not self-contained ({pattern})"] if re.search(pattern, text) else []
    styles = re.findall(r"<style>(.*?)</style>", text, re.S)
    if len(styles) > 1 or (styles and not ALLOWED_CSS.fullmatch(styles[0])):
        problems.append("style holds more than the motion rules")
    if problems:
        raise SystemExit(f"{path.name}: " + "; ".join(problems))
    return len(data)


def build(faces, line, eyebrow, out: Path | None):
    """Build every asset; write to `out` when given. Returns {file name: (svg text, viewBox size)}."""
    if len(eyebrow) > 50:
        raise SystemExit(f"eyebrow has {len(eyebrow)} characters (max 50)")
    files = {}
    svg, cv = hero_horizon(faces, line, eyebrow)
    check_layout("hero.svg", cv, (M, 24), clearance=24)
    check_motion("hero.svg", cv)
    files["hero.svg"] = (svg, (W, H))
    for index, spec in enumerate(CARDS):
        svg, cv = card(faces, spec, index)
        check_layout(spec["slug"], cv, (PAD, 14), clearance=8)
        check_motion(spec["slug"], cv)
        files[f"card-{spec['slug']}.svg"] = (svg, (CW, CH))
    for spec in BADGES:
        svg, cv = badge(faces, spec)
        check_layout(f"badge-{spec['slug']}", cv, (B_INSET + 8, 6), clearance=5)
        files[f"badge-{spec['slug']}.svg"] = (svg, (cv.w, cv.h))
    if out:
        out.mkdir(parents=True, exist_ok=True)
        for name, (svg, _) in files.items():
            (out / name).write_text(svg, encoding="utf-8", newline="\n")
    return files


def main() -> None:
    if DISPLAY.exists():
        use_display(json.loads(DISPLAY.read_text(encoding='utf-8'))['profile'])
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fonts", type=Path, required=True, help="folder with NotoSans-Regular/Bold.ttf")
    parser.add_argument("--line", default=LINE, help="positioning line (up to twelve words)")
    parser.add_argument("--eyebrow", default=EYEBROW, help="eyebrow, at most 50 characters (set in capitals)")
    parser.add_argument('--profile', type=Path, help='refresh the public display snapshot and README from the website profile.json')
    args = parser.parse_args()
    if not DISPLAY.exists() and not args.profile:
        raise SystemExit('missing data/profile-display.json; pass --profile with the website fact source')
    if args.profile:
        data = public_display(json.loads(args.profile.read_text(encoding='utf-8')))
        canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        snapshot = {'generated_from': 'Hanyuyuan6/hanyuyuan6.github.io:profile.json',
                    'source_public_fields_sha256': hashlib.sha256(canonical).hexdigest(), 'profile': data}
        DISPLAY.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        use_display(data)
        # An explicit layout override still takes precedence over the refreshed display snapshot.
        if args.line == parser.get_default('line'):
            args.line = LINE
        if args.eyebrow == parser.get_default('eyebrow'):
            args.eyebrow = EYEBROW
        sync_readme(data)
    if len(args.line.split()) > 12:
        raise SystemExit("the positioning line has more than twelve words")
    faces = {k: Face(args.fonts / f"NotoSans-{v}.ttf") for k, v in (("regular", "Regular"), ("bold", "Bold"))}
    for alternative in STRESS_LINES:             # layouts must hold for other lines too
        build(faces, alternative, args.eyebrow, None)
    files = build(faces, args.line, args.eyebrow, ASSETS)
    for name, (_, view) in files.items():
        print(f"{name}: {check_file(ASSETS / name, view):,} bytes")
    lightest = C["bg1"]                          # text is checked against the lighter gradient stop
    for role in ("ink", "muted"):
        ratio = contrast(C[role], lightest)
        if ratio < 4.5:
            raise SystemExit(f"{role} contrast {ratio:.2f}:1 is below 4.5:1")
        print(f"contrast {role} on {lightest}: {ratio:.2f}:1")
    print(f"stress-tested lines: {len(STRESS_LINES)}; all geometry and motion checks passed")


if __name__ == "__main__":
    main()
