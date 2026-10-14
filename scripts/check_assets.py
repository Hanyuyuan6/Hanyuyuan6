#!/usr/bin/env python3
"""Check the README's SVGs independently of the generator: read the shipped files, render them.

    python scripts/check_assets.py              # check assets/ (exit 1 on any failure)
    python scripts/check_assets.py --self-test  # seeded faults: each must be rejected

Needs Pillow and librsvg's rsvg-convert. Never imports scripts/build_assets.py: it judges the files.

1. Limits: well-formed XML, exact viewBox, <= 150 KB, UTF-8 with LF, nothing external or scripted
   (<text>, <image>, href, url() other than #ids, @import, @font-face, font-family, <script>,
   <foreignObject>, event-handler attributes, javascript:); SMIL (<animate*>, <set>) is forbidden.
2. Contrast: every text fill against the lighter background stop (WCAG 2.x, >= 4.5:1).
   Data: data/portrait-signal.json must hold the pinned reference values (REFERENCE_SHA256; change the
   pin only with a deliberate new measurement). Each card must have exactly one measured trace, whose
   24 knots are an exact linear image of its pinned, nonoverlapping portrait interval (uniform x,
   residual <= 0.01 px). The four intervals are independently scaled decorative identity motifs.
   The hero is a synthetic concept, checked separately for its disclaimer, brain contour, seven slices,
   cortical grooves and 72 fixed points. A conceptual light trace must never claim measured amplitudes.
3. Overlap, on renders (librsvg, 4x): every text run and the graphics (every non-text shape) are
   rendered alone; text keeps a minimum distance from the graphics, text runs never overlap, and
   nothing enters the outer margin.
4. Badges: the same limits, contrast and overlap checks; height 28, no data trace.
5. Motion policy: at most one <style>, inside <defs>. Its CSS holds only `animation` on class selectors,
   @keyframes animating opacity, stroke-dasharray or stroke-dashoffset, one @media
   (prefers-reduced-motion: reduce) block that sets `animation: none` on every animated selector, and
   one @media (max-width: Npx) block that only swaps the full layout (class X-full) for the compact one
   (group X-compact, display="none" by attribute, so renderers without CSS show the full layout). Text is
   never animated. One-shot animations fill both ways and settle within 4.5 s; a loop may only fade an
   element that is invisible when static, from 0 back to 0, with a period of at least 4 s.
6. Motion, rendered: frames are computed from the file's own CSS (an evaluator of that subset) and
   rendered. The settled frame must equal the static render; traces only grow and fades only rise; the
   every loop at its own brightest keeps the text clearance and the outer margin.
7. Compact view: rebuilt as its own document (as a narrow image shows it), it must pass 1-3, keep the
   data trace or brain illustration, and replace every full-layout text run.

Origin: the identity checker (design/claude/scripts/check_identity.py), whose blanket ban on
@keyframes and animation is replaced by the stricter motion policy in 5-6; every other check is kept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIGNAL = json.loads((ROOT / "data" / "portrait-signal.json").read_text(encoding="utf-8"))["values"]
REFERENCE_SHA256 = "b467eab0bbeb082f254e6b0e2fdba790b1c06e013a399a83666954aaf5de5b02"  # compact JSON of the values
NS = "{http://www.w3.org/2000/svg}"
EXPECT = {  # file: (viewBox size, min text-to-graphics clearance in px, outer margin in px)
    "hero.svg": ((1280, 340), 24, 24),
    "card-stsf-tpls.svg": ((400, 150), 8, 14), "card-remote-gpu-trainer.svg": ((400, 150), 8, 14),
    "card-shsi.svg": ((400, 150), 8, 14), "card-ldgi.svg": ((400, 150), 8, 14),
}
CARD_START = {'card-stsf-tpls.svg': 0, 'card-remote-gpu-trainer.svg': 24,
              'card-shsi.svg': 48, 'card-ldgi.svg': 72}
BADGE = re.compile(r"badge-[a-z]+\.svg")  # badges: height 28, width 60-260, clearance 5, margin 6
SCALE = 4
RSVG = shutil.which("rsvg-convert") or ("/opt/homebrew/bin/rsvg-convert" if Path("/opt/homebrew/bin/rsvg-convert").exists() else None)
MAX_SETTLE, MIN_PERIOD = 4.5, 4.0


def check_signal(values) -> list[str]:
    digest = hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()
    return [] if digest == REFERENCE_SHA256 else [f"data/portrait-signal.json differs from the pinned reference ({digest[:12]})"]


def luminance(c):
    ch = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def render(svg_text: str, out: Path, scale=SCALE, width=None):
    src = out.with_suffix(".svg")
    src.write_text(svg_text, encoding="utf-8")
    args = [RSVG] + (["-w", str(width)] if width else ["-z", str(scale)]) + ["-o", str(out), str(src)]
    subprocess.run(args, check=True)
    return Image.open(out).convert("RGBA")


def alone(root: ET.Element, keep: ET.Element) -> str:
    """The same document with only <defs> and one element: renders that element by itself."""
    clone = ET.Element(root.tag, root.attrib)
    for child in root:
        if child.tag == NS + "defs" or child is keep:
            clone.append(child)
    return ET.tostring(clone, encoding="unicode")


# ------------------------------------------------------------------------------ CSS motion
TIMING = {"linear": (0, 0, 1, 1), "ease": (.25, .1, .25, 1), "ease-in": (.42, 0, 1, 1),
          "ease-out": (0, 0, .58, 1), "ease-in-out": (.42, 0, .58, 1)}
ANIMATED = ("opacity", "stroke-dasharray", "stroke-dashoffset")


def bezier(p, x):
    """CSS cubic-bezier timing: progress at time fraction x."""
    x1, y1, x2, y2 = p
    if (x1, y1, x2, y2) == (0, 0, 1, 1):
        return x
    b = lambda a, c, s: 3 * a * (1 - s) ** 2 * s + 3 * c * (1 - s) * s * s + s ** 3  # noqa: E731
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if b(x1, x2, mid) < x else (lo, mid)
    return b(y1, y2, (lo + hi) / 2)


def split_blocks(css: str):
    """Top-level CSS items as (prelude, body) pairs; raises on unbalanced braces."""
    items, depth, start, prelude = [], 0, 0, ""
    for i, ch in enumerate(css):
        if ch == "{":
            if depth == 0:
                prelude, start = css[start:i].strip(), i + 1
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced braces")
            if depth == 0:
                items.append((prelude, css[start:i]))
                start = i + 1
    if depth or css[start:].strip():
        raise ValueError("unbalanced braces or trailing text")
    return items


def declarations(body: str):
    out = {}
    for part in body.split(";"):
        if part.strip():
            k, _, v = part.partition(":")
            out[k.strip()] = v.strip()
    return out


def parse_animation(value: str):
    tokens = re.findall(r"cubic-bezier\([^)]*\)|[^\s,]+", value)
    if "," in re.sub(r"\([^)]*\)", "", value):
        raise ValueError("more than one animation on one selector")
    spec = {"name": None, "times": [], "timing": TIMING["ease"], "iterations": 1.0, "direction": "normal", "fill": "none"}
    for tok in tokens:
        if re.fullmatch(r"\d*\.?\d+m?s", tok):
            spec["times"].append(float(tok[:-2]) / 1000 if tok.endswith("ms") else float(tok[:-1]))
        elif tok in TIMING:
            spec["timing"] = TIMING[tok]
        elif tok.startswith("cubic-bezier("):
            spec["timing"] = tuple(float(v) for v in tok[13:-1].split(","))
        elif tok == "infinite":
            spec["iterations"] = math.inf
        elif re.fullmatch(r"\d*\.?\d+", tok):
            spec["iterations"] = float(tok)
        elif tok in ("normal", "reverse", "alternate", "alternate-reverse"):
            spec["direction"] = tok
        elif tok in ("none", "forwards", "backwards", "both"):
            spec["fill"] = tok
        elif tok in ("running", "paused") or tok.startswith("steps(") or tok in ("step-start", "step-end"):
            raise ValueError(f"unsupported animation token {tok!r}")
        else:
            spec["name"] = tok
    spec["duration"] = spec["times"][0] if spec["times"] else 0.0
    spec["delay"] = spec["times"][1] if len(spec["times"]) > 1 else 0.0
    return spec


def parse_motion(css: str):
    """-> dict: anims {class: spec}, frames {name: [(fraction, {prop: value})]}, reduced {class},
    display [(class, none|inline)] from the width block, problems [str]."""
    out = {"anims": {}, "frames": {}, "reduced": set(), "display": [], "problems": []}
    try:
        items = split_blocks(css)
    except ValueError as e:
        out["problems"].append(f"css: {e}")
        return out
    for prelude, body in items:
        if prelude.startswith("@keyframes "):
            name, steps = prelude[11:].strip(), []
            for sel, decl in split_blocks(body):
                props = declarations(decl)
                if set(props) - set(ANIMATED):
                    out["problems"].append(f"@keyframes {name} animates {sorted(set(props) - set(ANIMATED))}")
                for key in sel.split(","):
                    key = key.strip()
                    frac = 0.0 if key == "from" else 1.0 if key == "to" else float(key.rstrip("%")) / 100
                    steps.append((frac, props))
            out["frames"][name] = sorted(steps, key=lambda s: s[0])
        elif re.fullmatch(r"@media\s*\(\s*max-width\s*:\s*\d+px\s*\)", prelude):
            for sel, decl in split_blocks(body):
                props = declarations(decl)
                if set(props) != {"display"} or props["display"] not in ("none", "inline") or not re.fullmatch(r"\.[A-Za-z0-9_-]+", sel.strip()):
                    out["problems"].append(f"width rule {sel!r} {props} is more than a display swap")
                else:
                    out["display"].append((sel.strip()[1:], props["display"]))
        elif re.fullmatch(r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)", prelude):
            for sel, decl in split_blocks(body):
                if declarations(decl) not in ({"animation": "none"}, {"animation-name": "none"}):
                    out["problems"].append(f"reduced-motion rule {sel!r} does more than stop animation")
                out["reduced"] |= {s.strip()[1:] for s in sel.split(",")}
        elif prelude.startswith("@"):
            out["problems"].append(f"at-rule not allowed: {prelude[:40]!r}")
        else:
            props = declarations(body)
            if set(props) != {"animation"}:
                out["problems"].append(f"rule {prelude!r} sets {sorted(props)}: only `animation` is allowed")
            for sel in prelude.split(","):
                sel = sel.strip()
                if not re.fullmatch(r"\.[A-Za-z0-9_-]+", sel):
                    out["problems"].append(f"selector {sel!r} is not a single class")
                    continue
                try:
                    out["anims"][sel[1:]] = parse_animation(props.get("animation", ""))
                except ValueError as e:
                    out["problems"].append(f"{sel}: {e}")
    return out


def numbers(v: str):
    return [float(x) for x in re.split(r"[\s,]+", v.strip()) if x]


def value_at(spec, steps, prop, t, static):
    """Animated value of `prop` at document time t, or None when the animation does not apply."""
    local = t - spec["delay"]
    total = spec["duration"] * spec["iterations"]
    if local < 0:
        if spec["fill"] not in ("backwards", "both"):
            return None
        p = 0.0
    elif local >= total:
        if spec["fill"] not in ("forwards", "both"):
            return None
        p = 1.0
    else:
        p = (local % spec["duration"]) / spec["duration"]
    keys = [(f, props[prop]) for f, props in steps if prop in props]
    if not keys:
        return None
    if keys[0][0] > 0:
        keys.insert(0, (0.0, static))
    if keys[-1][0] < 1:
        keys.append((1.0, static))
    for (fa, va), (fb, vb) in zip(keys, keys[1:]):
        if fa <= p <= fb:
            f = 0.0 if fb == fa else bezier(spec["timing"], (p - fa) / (fb - fa))
            if va == "none" or vb == "none":
                return va if f < 0.5 else vb
            a, b = numbers(va), numbers(vb)
            if len(a) != len(b):
                return va if f < 0.5 else vb
            return " ".join(f"{x + (y - x) * f:.4f}" for x, y in zip(a, b))
    return keys[-1][1]


class Motion:
    """The file's CSS, parsed and checked for placement; `frame(t)` evaluates it at a moment."""

    def __init__(self, root: ET.Element):
        styles = list(root.iter(NS + "style"))
        self.css = "".join(s.text or "" for s in styles)
        self.problems = []
        if len(styles) > 1:
            self.problems.append("more than one <style>")
        defs = root.find(NS + "defs")
        if styles and (defs is None or styles[0] not in list(defs)):
            self.problems.append("<style> is not a child of <defs>")
        parsed = parse_motion(self.css) if self.css else {"anims": {}, "frames": {}, "reduced": set(), "display": [], "problems": []}
        self.anims, self.frames, self.reduced, self.display = parsed["anims"], parsed["frames"], parsed["reduced"], parsed["display"]
        self.problems += parsed["problems"]
        self.elements, seen = {}, {}
        for el in root.iter():
            for cls in (el.get("class") or "").split():
                seen.setdefault(cls, []).append(el)
                self.elements[cls] = el
        for cls in self.anims:
            if len(seen.get(cls, [])) > 1:
                self.problems.append(f"animated class {cls} is used twice")

    def settle(self):
        return max((s["delay"] + s["duration"] * s["iterations"] for s in self.anims.values() if s["iterations"] != math.inf), default=0.0)

    def loops(self):
        return {c: s for c, s in self.anims.items() if s["iterations"] == math.inf}

    def frame(self, root_text: str, t: float, reduced=False) -> str:
        """The document at time t with every animated value written into the element's style."""
        root = ET.fromstring(root_text)
        for style in root.iter(NS + "style"):
            style.text = ""
        if reduced:
            return ET.tostring(root, encoding="unicode")
        index = {}
        for el in root.iter():
            for cls in (el.get("class") or "").split():
                index[cls] = el
        for cls, spec in self.anims.items():
            el = index.get(cls)
            steps = self.frames.get(spec["name"])
            if el is None or steps is None:
                continue
            decl = []
            for prop in ANIMATED:
                static = {"opacity": el.get("opacity", "1"), "stroke-dashoffset": "0", "stroke-dasharray": "none"}[prop]
                v = value_at(spec, steps, prop, t, static)
                if v is not None:
                    decl.append(f"{prop}:{v}")
            if decl:
                el.set("style", ";".join(decl))
        return ET.tostring(root, encoding="unicode")


def check_motion(path: Path, text: str, root: ET.Element, texts, tmp: Path, report: dict):
    """Sections 5 (policy) and 6 (rendered frames). Returns (failures, (motion, loop peak time) or None)."""
    fails = []
    mo = Motion(root)
    fails += mo.problems
    if not mo.anims:
        if mo.css.strip():
            fails.append("style present without animation")
        return fails, None
    report["motion"] = {"settles_s": round(mo.settle(), 2), "loops": sorted(mo.loops())}
    text_ids = {id(el) for el in texts}
    for cls, spec in mo.anims.items():
        el = mo.elements.get(cls)
        if el is None:
            fails.append(f"animation on .{cls}, which no element carries")
            continue
        if id(el) in text_ids:
            fails.append(f".{cls} animates a text run")
        if spec["name"] not in mo.frames:
            fails.append(f".{cls}: @keyframes {spec['name']} missing")
        if spec["direction"] != "normal":
            fails.append(f".{cls}: direction {spec['direction']}")
        if cls not in mo.reduced:
            fails.append(f".{cls} keeps moving under prefers-reduced-motion")
        if spec["iterations"] == math.inf:
            steps = mo.frames.get(spec["name"], [])
            props = set().union(*(p.keys() for _, p in steps)) if steps else set()
            ends = [p.get("opacity") for f, p in steps if f in (0.0, 1.0)]
            if props != {"opacity"} or el.get("opacity") != "0" or ends.count("0") < 2 or spec["duration"] < MIN_PERIOD:
                fails.append(f".{cls}: a loop may only fade an element invisible when static, 0 -> 0, period >= {MIN_PERIOD} s")
        elif spec["fill"] != "both":
            fails.append(f".{cls}: one-shot animation must fill both ways (fill {spec['fill']})")
    if mo.settle() > MAX_SETTLE:
        fails.append(f"motion settles at {mo.settle():.2f} s (> {MAX_SETTLE} s)")
    if fails:
        return fails, None
    # the settled frame (loops at a whole number of periods) equals the static frame
    periods = [s["duration"] for s in mo.loops().values()]
    t_end = mo.settle() + 0.001
    if periods:
        start = max(s["delay"] for s in mo.loops().values())
        t_end = max(t_end, start + periods[0] * math.ceil((t_end - start) / periods[0]))
    static = render(mo.frame(text, 0, reduced=True), tmp / f"{path.stem}-static.png")
    settled = render(mo.frame(text, t_end), tmp / f"{path.stem}-settled.png")
    worst = max(b[1] for b in ImageChops.difference(static, settled).getextrema())
    report["motion"]["settled_vs_static_max_diff"] = worst
    if worst > 8:
        fails.append(f"settled frame differs from the static frame (max channel difference {worst})")
    # traces only grow, fades only rise (one-shot), sampled every 20 ms up to the settle time
    for cls, spec in mo.anims.items():
        if spec["iterations"] == math.inf:
            continue
        steps = mo.frames[spec["name"]]
        prev = {}
        t = 0.0
        while t <= mo.settle() + 0.02:
            for prop, sign in (("stroke-dashoffset", -1), ("opacity", 1)):
                v = value_at(spec, steps, prop, t, "0" if prop != "opacity" else mo.elements[cls].get("opacity", "1"))
                if v is None:
                    continue
                x = numbers(v)[0]
                if prop in prev and sign * (x - prev[prop]) < -1e-6:
                    fails.append(f".{cls}: {prop} reverses at t={t:.2f} s")
                    break
                prev[prop] = x
            t += 0.02
    peaks = []  # every loop at its brightest, not only the final declared loop
    for cls, spec in mo.loops().items():
        steps = mo.frames[spec["name"]]
        best = max(steps, key=lambda s: float(s[1].get("opacity", 0)))
        peak = spec["delay"] + best[0] * spec["duration"] + 3 * spec["duration"]
        peaks.append((cls, peak))
    return fails, (mo, peaks)


def compact_view(text: str, display):
    """The document as a narrow image shows it: elements of the class set to none are removed, the group
    set to inline loses its display attribute and its children move up to the root (as the full layout's
    are), and the style is dropped. Returns None when the file has no compact view."""
    hide = {c for c, d in display if d == "none"}
    show = {c for c, d in display if d == "inline"}
    if not show:
        return None
    root = ET.fromstring(text)
    out = ET.Element(root.tag, root.attrib)
    for child in root:
        classes = set((child.get("class") or "").split())
        if child.tag == NS + "defs":
            for style in child.findall(NS + "style"):
                child.remove(style)
            out.append(child)
        elif classes & hide:
            continue
        elif classes & show:
            if child.tag != NS + "g" or child.get("display") != "none":
                raise ValueError("the compact view must be a group hidden by attribute")
            for grandchild in child:
                out.append(grandchild)
        else:
            out.append(child)
    return ET.tostring(out, encoding="unicode")


# ---------------------------------------------------------------------------------- checks
def check_concept(root: ET.Element, report: dict):
    """Inspect the shipped concept's population, labels and visibility without the generator."""
    fails = []
    desc = (root.findtext(NS + 'desc') or '').lower()
    for phrase in ('synthetic concept illustration', 'schematic brain', 'not measured data'):
        if phrase not in desc:
            fails.append(f'brain illustration description is missing {phrase!r}')
    if 'first ' in desc or 'drawn to linear scale' in desc:
        fails.append('a synthetic brain illustration claims measured signal samples')
    groups = [e for e in root.iter(NS + 'g') if e.get('id') == 'hero-concept']
    if len(groups) != 1 or groups[0].get('data-illustration') != 'synthetic-optical-brain':
        fails.append('expected one explicitly synthetic brain concept group')
        return fails
    parent = {child: el for el in root.iter() for child in el}

    def visible(el):
        opacity = 1.0
        while el is not None:
            opacity *= float(el.get('opacity', '1'))
            if el.get('display') == 'none':
                return False
            el = parent.get(el)
        return opacity >= .1

    population = {}
    for cls, tag, expected in (('brain-outline', 'path', 1), ('slice', 'path', 7),
                               ('cortical-groove', 'path', 8), ('sample', 'circle', 60),
                               ('constellation', 'circle', 12), ('trace', 'path', 1),
                               ('optical-input', 'path', 1)):
        elements = [e for e in groups[0].iter(NS + tag) if f'hero-{cls}' in (e.get('class') or '').split()]
        population[cls] = len(elements)
        if len(elements) != expected:
            fails.append(f'brain concept {cls}: expected {expected}, found {len(elements)}')
        for el in elements:
            if not visible(el):
                fails.append(f'brain concept {cls} is invisible in the static illustration')
            if tag == 'circle' and float(el.get('r', '0')) < .5:
                fails.append(f'brain concept {cls} has no visible radius')
            if tag == 'path' and len(re.findall(r'-?\d+(?:\.\d+)?', el.get('d', ''))) < 12:
                fails.append(f'brain concept {cls} has incomplete geometry')
        if cls == 'slice' and {e.get('data-slice') for e in elements} != {str(i) for i in range(1, 8)}:
            fails.append('brain concept must contain slices 1 through 7 exactly once')
    report['concept'] = population
    return fails


def check(path: Path, tmp: Path):
    """The full (static) view and its motion, then the compact view if the file has one."""
    data = path.read_bytes()
    fails, report = check_text(path, data, tmp)
    root = ET.fromstring(data.decode("utf-8"))
    mo = Motion(root) if list(root.iter(NS + "style")) else None
    if mo and mo.display:
        try:
            compact = compact_view(data.decode("utf-8"), mo.display)
        except ValueError as e:
            return fails + [f"compact view: {e}"], report
        if compact:
            hidden = {c for c, d in mo.display if d == "none"}
            full_texts = [el for el in root if el.tag == NS + "path" and el.get("fill", "none") != "none"]
            if any(not (set((el.get("class") or "").split()) & hidden) for el in full_texts):
                fails.append("compact view keeps some full-layout text (every full text run must swap)")
            cfails, creport = check_text(path, compact.encode("utf-8"), tmp, view="compact")
            fails += [f"compact view: {f}" for f in cfails]
            report["compact"] = {k: v for k, v in creport.items() if k in ("texts", "min_contrast", "samples", "concept", "clearance (static)")}
            if creport.get("samples") != report.get("samples"):
                fails.append("compact view drops the data trace")
    return fails, report


def check_text(path: Path, data: bytes, tmp: Path, view: str = "full"):
    """Sections 1-4 on one document (the file, or its compact view), and 5-6 on the full view."""
    is_badge = bool(BADGE.fullmatch(path.name))
    text = data.decode("utf-8")
    fails = []
    if len(data) > 150 * 1024:
        fails.append(f"{len(data)} bytes > 150 KB")
    if b"\r" in data:
        fails.append("CR line endings")
    for pattern in (r"<text\b", r"<image\b", r"href\s*=", r"url\((?!#)", r"@import", r"font-family", r"<script\b",
                    r"<animate", r"<set\b", r"@font-face", r"<foreignObject", r"\son[a-z]+\s*=", r"javascript:"):
        if re.search(pattern, text):
            fails.append(f"forbidden: {pattern}")
    root = ET.fromstring(text)
    if is_badge:
        vb = [float(v) for v in root.get("viewBox", "").split()]
        if len(vb) != 4 or vb[:2] != [0, 0] or vb[3] != 28 or not 60 <= vb[2] <= 260:
            fails.append(f"viewBox {root.get('viewBox')}")
        (vw, vh), clearance, margin = (vb[2], vb[3]), 5, 6
    elif path.name in EXPECT:
        (vw, vh), clearance, margin = EXPECT[path.name]
        if root.get("viewBox") != f"0 0 {vw} {vh}":
            fails.append(f"viewBox {root.get('viewBox')}")
    else:
        return fails + [f"unexpected file {path.name}"], {}
    body = [el for el in root if el.tag not in (NS + "defs", NS + "style") and not el.tag.endswith(("title", "desc"))]
    tile = re.fullmatch(r"url\(#(.+)\)", body[0].get("fill", "")) if body else None  # first shape = the tile/card
    gradient = root.find(f"{NS}defs/{NS}linearGradient[@id='{tile.group(1)}']") if tile else None
    if gradient is None:
        return fails + ["first shape is not a tile filled by a gradient in <defs>"] + check_motion(path, text, root, [], tmp, {})[0], {}
    lighter = max((s.get("stop-color") for s in gradient), key=luminance)
    ids = [el.get("id") for el in root.iter() if el.get("id")]
    if len(ids) != len(set(ids)) or not all(i.startswith(path.stem) for i in ids):
        fails.append(f"ids not unique or not prefixed with the file name: {ids}")
    texts = [el for el in body[1:] if el.tag == NS + "path" and el.get("fill", "none") != "none"]
    report = {"bytes": len(data), "texts": len(texts)}
    for el in texts:
        ratio = contrast(el.get("fill"), lighter)
        if ratio < 4.5:
            fails.append(f"text fill {el.get('fill')} contrast {ratio:.2f}:1")
    report["min_contrast"] = round(min((contrast(el.get("fill"), lighter) for el in texts), default=99), 2)
    # Keep conceptual brain graphics separate from the cards' measured portrait data.
    traces = [el for el in body[1:] if el.tag == NS + 'path' and f'{path.stem}-trace' in (el.get('class') or '').split()]
    if path.name == 'hero.svg':
        fails += check_concept(root, report)
    elif not is_badge and len(traces) != 1:
        fails.append(f'a research card must carry exactly one measured trace, found {len(traces)}')
    # data fidelity: the card trace's knots must remain an exact linear image of 24 real samples
    for el in traces if path.name != 'hero.svg' else []:
        if el.get('fill') != 'none':
            fails.append('the measured trace is not an unfilled path')
        else:
            nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", el.get("d"))]
            knots = [(nums[0], nums[1])] + [(nums[i + 4], nums[i + 5]) for i in range(2, len(nums), 6)]
            start = CARD_START.get(path.name, 0)
            values = SIGNAL[start:start + len(knots)]
            ys = [y for _, y in knots]
            mv, my = sum(values) / len(values), sum(ys) / len(ys)
            slope = sum((v - mv) * (y - my) for v, y in zip(values, ys)) / sum((v - mv) ** 2 for v in values)
            worst = max(abs(my + slope * (v - mv) - y) for v, y in zip(values, ys))
            steps = [b[0] - a[0] for a, b in zip(knots, knots[1:])]
            report["samples"] = len(knots)
            report['sample_interval'] = [start + 1, start + len(knots)]
            if len(knots) != 24:
                fails.append(f'a card must display 24 measured samples, found {len(knots)}')
            if slope >= 0 or worst > 0.01 or max(steps) - min(steps) > 0.02:
                fails.append(f"trace is not portrait samples {start + 1} through {start + len(knots)} at linear scale (residual {worst:.3f} px)")
            if f"samples {start + 1} through {start + len(knots)} " not in text:
                fails.append(f"description does not state the {len(knots)} portrait samples drawn")
            for phrase in ('Portrait-derived decorative motif', 'independently linearly scaled', 'not project measurements or performance'):
                if phrase not in text:
                    fails.append(f'card sparkline description is missing {phrase!r}')
    if is_badge and "samples" in report:
        fails.append("a badge carries a data trace")
    if not RSVG:
        return fails + ["rsvg-convert not found: render checks skipped"], report
    motion_fails, motion = check_motion(path, text, root, texts, tmp, report) if view == "full" else ([], None)
    fails += motion_fails

    def graphics_doc(src_text, at=None):
        """Defs plus every graphic (every non-text shape), optionally at time `at`."""
        src = motion[0].frame(src_text, at) if (motion and at is not None) else src_text
        r = ET.fromstring(src)
        b = [el for el in r if el.tag not in (NS + "defs", NS + "style") and not el.tag.endswith(("title", "desc"))]
        clone = ET.Element(r.tag, r.attrib)
        for child in r:
            if child.tag == NS + "defs":
                clone.append(child)
        for el in b[1:]:
            if not (el.tag == NS + "path" and el.get("fill", "none") != "none"):
                clone.append(el)
        return ET.tostring(clone, encoding="unicode")

    frames = [("static", graphics_doc(text))]
    if motion:
        for cls, peak in motion[1]:
            frames.append((f'loop peak {cls}', graphics_doc(text, peak)))
    boxes = []
    for i, el in enumerate(texts):  # ElementTree does not re-parent on append, so root stays whole
        img = render(alone(root, el), tmp / f"{path.stem}-{view}-text{i}.png")
        boxes.append(img.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox())
    for label, doc in frames:
        alpha = render(doc, tmp / f"{path.stem}-{view}-graphics-{label.replace(' ', '-')}.png").getchannel("A")
        sig_box = alpha.point(lambda a: 255 if a > 24 else 0).getbbox()
        if sig_box is None:
            continue
        crop = alpha.crop(sig_box)
        cw, px = crop.size[0], crop.load()
        sig_pixels = [(sig_box[0] + x, sig_box[1] + y) for y in range(crop.size[1]) for x in range(cw) if px[x, y] > 24]
        for i, box in enumerate(boxes):
            x0, y0, x1, y1 = box
            nearest = min(max(x0 - x, x - x1, 0) ** 2 + max(y0 - y, y - y1, 0) ** 2 for x, y in sig_pixels) ** 0.5 / SCALE
            report.setdefault(f"clearance ({label})", []).append(round(nearest, 1))
            if nearest < clearance:
                fails.append(f"text run {i} is {nearest:.1f} px from the graphics ({label}; < {clearance})")
        x0, y0, x1, y1 = (v / SCALE for v in sig_box)
        if x0 < margin - 2 or y0 < margin or x1 > vw - margin + 0.5 or y1 > vh - margin:
            fails.append(f"graphics ({label}) inside the outer margin: {(round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))}")
    for a in range(len(boxes)):
        for b in range(a + 1, len(boxes)):
            p, q = boxes[a], boxes[b]
            if p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]:
                fails.append(f"text runs {a} and {b} overlap")
    for i, box in enumerate(boxes):
        x0, y0, x1, y1 = (v / SCALE for v in box)
        if x0 < margin - 2 or y0 < margin or x1 > vw - margin + 0.5 or y1 > vh - margin:
            fails.append(f"text {i} inside the outer margin: {(round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))}")
    return fails, report


def check_all(folder: Path = ASSETS) -> int:
    failed = bool(check_signal(SIGNAL))
    print("ok   data/portrait-signal.json matches the pinned reference" if not failed else "FAIL " + check_signal(SIGNAL)[0])
    names = list(EXPECT) + sorted(p.name for p in folder.glob("badge-*.svg"))
    with tempfile.TemporaryDirectory() as t:
        for name in names:
            fails, report = check(folder / name, Path(t))
            summary = {k: v for k, v in report.items() if k in ("bytes", "min_contrast", "samples", "sample_interval", "concept", "motion", "compact")}
            print(f"{'FAIL' if fails else 'ok  '} {name}: {summary}" + "".join(f"\n     - {f}" for f in fails))
            failed |= bool(fails)
    return 1 if failed else 0


# ------------------------------------------------------------------------------- self-test
def _sub(pattern, repl, flags=0):
    def mutate(s):
        out, n = re.subn(pattern, repl, s, count=1, flags=flags)
        if not n:
            raise LookupError(f"fault pattern not found: {pattern}")
        return out
    return mutate


def _compact_up(s):  # lift the compact view's first text run onto the sparkline
    key = '-compact" display="none"><path '
    i = s.index(key) + len(key)
    return s[:i] + 'transform="translate(0,-50)" ' + s[i:]


FAULTS = [  # (what goes wrong, file, mutation); each must make check() fail
    ("trace ends partly drawn", "hero.svg", _sub(r"stroke-dasharray:none", "stroke-dasharray:10 1000")),
    ("reduced motion skips the halo", "hero.svg", _sub(r"\{\.hero-halo,", "{")),
    ("loop on a visible element", "hero.svg", _sub(r'(<circle class="hero-halo"[^>]*?)opacity="0"', r'\1opacity="1"')),
    ("text run animated", "hero.svg", lambda s: _sub(r'<path class="hero-full"', '<path class="hero-full hero-x"')(s)
     .replace("<style>", "<style>.hero-x{animation:hero-pixel .4s linear 0s both}", 1)),
    ("transform in keyframes", "hero.svg", _sub(r"@keyframes hero-pixel\{0%\{opacity:0\}", "@keyframes hero-pixel{0%{opacity:0;transform:scale(2)}")),
    ("settles after 4.5 s", "hero.svg", _sub(r"(\.hero-trace\{animation:hero-trace [\d.]+s linear )[\d.]+s", r"\g<1>3s")),
    ("style outside defs", "hero.svg", _sub(r"<defs>(<style>.*?</style>)", r"\1<defs>", re.S)),
    ("SMIL element", "hero.svg", _sub(r"</svg>", '<animate attributeName="opacity" from="0" to="1" dur="1s"/></svg>')),
    ("one-shot fill forwards only", "card-shsi.svg", _sub(r"(\.card-shsi-trace\{animation:[^}]*?) both\}", r"\1 forwards}")),
    ("dash offset reverses mid-draw", "card-shsi.svg", _sub(r"(@keyframes card-shsi-trace\{0%\{[^}]*\}[\d.]+%\{stroke-dashoffset:)[\d.]+", r"\g<1>200")),
    ("compact text collides with the sparkline", "card-remote-gpu-trainer.svg", _compact_up),
    ("compact view keeps a full text run", "card-ldgi.svg", _sub(r'<path class="card-ldgi-full"', "<path")),
    ("width rule does more than swap", "card-ldgi.svg", _sub(r"\.card-ldgi-compact\{display:inline\}", ".card-ldgi-compact{display:inline;opacity:.5}")),
    ("data: one knot moved 0.5 px", "card-shsi.svg", lambda s: re.sub(r'(<path class="card-shsi-trace" d="M[\d.]+ [\d.]+C[\d.]+ [\d.]+ [\d.]+ [\d.]+ [\d.]+ )([\d.]+)',
                                                                  lambda m: m.group(1) + f"{float(m.group(2)) + 0.5:.2f}", s, count=1)),
    ("contrast: text fill too dark", "card-shsi.svg", _sub(r'fill="#a9a1bd"', 'fill="#4a4258"')),
    ("badge label too dark", "badge-orcid.svg", _sub(r'fill="#f3efff"', 'fill="#3a3248"')),
    ("external reference", "badge-email.svg", _sub(r"</svg>", '<image href="https://example.com/x.png"/></svg>')),
    ("brain disclaimer removed", "hero.svg", _sub(r'Synthetic concept illustration:', 'Clinical reconstruction:')),
    ("brain outline hidden", "hero.svg", _sub(r'(<path class="hero-brain-outline")', r'\1 opacity="0"')),
    ("tomography slice omitted", "hero.svg", _sub(r'<path class="hero-slice" data-slice="4"[^>]*/>', '')),
    ("constellation point omitted", "hero.svg", _sub(r'<circle class="hero-constellation"[^>]*/>', '')),
    ("early loop crosses the margin", "hero.svg", _sub(r'(<g class="hero-photon-0" opacity="0">)<circle cx="[\d.]+"', r'\1<circle cx="2"')),
]


def self_test() -> int:
    """The pristine files must pass; then every seeded fault must be rejected (a crash is not a catch)."""
    bad = 0
    with tempfile.TemporaryDirectory() as t:
        tmp, work = Path(t), Path(t) / "faults"
        work.mkdir()
        for name in sorted({f for _, f, _ in FAULTS}):
            fails, _ = check(ASSETS / name, tmp)
            print(f"{'ok    ' if not fails else 'BROKEN'} pristine {name}" + (f": {fails[0]}" if fails else ""))
            bad += bool(fails)
        for label, name, mutate in FAULTS:
            try:
                (work / name).write_text(mutate((ASSETS / name).read_text(encoding="utf-8")), encoding="utf-8")
                fails, _ = check(work / name, tmp)
            except Exception as e:  # noqa: BLE001  (a crash or a stale pattern counts as a miss)
                fails = None
                print(f"ERROR  {label}: {type(e).__name__}: {e}")
            print(f"{'caught' if fails else 'MISSED'} {label}" + (f": {fails[0][:100]}" if fails else ""))
            bad += not fails
            (work / name).unlink(missing_ok=True)
    data_fault = check_signal([SIGNAL[0] + 1e-6] + SIGNAL[1:])
    print(f"{'caught' if data_fault else 'MISSED'} data: one reference value changed" + (f": {data_fault[0]}" if data_fault else ""))
    bad += not data_fault
    total = len(FAULTS) + 1
    print(f"{total}/{total} faults caught; pristine files pass" if not bad else f"self-test FAILED ({bad} problems)")
    return 1 if bad else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--self-test", action="store_true", help="seeded faults must be rejected; pristine files must pass")
    sys.exit(self_test() if parser.parse_args().self_test else check_all())
