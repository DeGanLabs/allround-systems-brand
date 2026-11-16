"""Trace the approved final logo mark (symbol only) into SVG masters."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import potrace
from PIL import Image
from potrace import Bitmap

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "variants" / "_source-final-logo.jpg"
OUT = ROOT / "svg"
PUBLIC = ROOT.parent / "public"

NAVY = "#0B243B"
ORANGE = "#F19E38"
PAPER = "#F5F3ED"
BLACK = "#000000"
WHITE = "#FFFFFF"


def load_mark_bitmap() -> tuple[np.ndarray, np.ndarray]:
    im = Image.open(SRC).convert("RGBA")
    a = np.array(im)
    rgb = a[:, :, :3].astype(np.float32)
    alpha = a[:, :, 3]
    # Navy ink (dark)
    navy = (rgb.mean(axis=2) < 95) & (alpha > 200)
    # Orange accent tip
    orange = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] < 160) & (rgb[:, :, 2] < 100) & (alpha > 200)
    ink = navy | orange
    ys, xs = np.where(ink)
    crop = ink[int(ys.min()) : int(ys.max()) + 1, int(xs.min()) : int(xs.max()) + 1]
    # Drop wordmark band (bottom ~28%)
    h, w = crop.shape
    mark = crop[: int(h * 0.70), :]
    orange_crop = orange[int(ys.min()) : int(ys.max()) + 1, int(xs.min()) : int(xs.max()) + 1][: int(h * 0.70), :]
    ch, cw = mark.shape
    pad = 36
    side = max(ch, cw) + pad * 2
    sq = np.zeros((side, side), dtype=bool)
    oq = np.zeros((side, side), dtype=bool)
    oy, ox = (side - ch) // 2, (side - cw) // 2
    sq[oy : oy + ch, ox : ox + cw] = mark
    oq[oy : oy + ch, ox : ox + cw] = orange_crop
    return sq, oq


def curve_points(curve: potrace.Curve) -> list[tuple[float, float]]:
    pts = [curve.start_point]
    for seg in curve.segments:
        if seg.is_corner:
            pts.append(seg.c)
            pts.append(seg.end_point)
        else:
            pts.append(seg.c1)
            pts.append(seg.c2)
            pts.append(seg.end_point)
    return [(p.x, p.y) for p in pts]


def touches_border(curve: potrace.Curve, side: int, margin: float = 2.0) -> bool:
    for x, y in curve_points(curve):
        if x <= margin or y <= margin or x >= side - margin or y >= side - margin:
            return True
    return False


def curves_to_d(path: potrace.Path, scale: float, side: int) -> str:
    parts: list[str] = []
    for curve in path:
        # Drop outer frame / full-bleed invert paths
        if touches_border(curve, side):
            continue
        sp = curve.start_point
        segs = [f"M{sp.x / scale:.2f} {sp.y / scale:.2f}"]
        for seg in curve.segments:
            if seg.is_corner:
                segs.append(
                    f"L{seg.c.x / scale:.2f} {seg.c.y / scale:.2f} "
                    f"L{seg.end_point.x / scale:.2f} {seg.end_point.y / scale:.2f}"
                )
            else:
                segs.append(
                    f"C{seg.c1.x / scale:.2f} {seg.c1.y / scale:.2f} "
                    f"{seg.c2.x / scale:.2f} {seg.c2.y / scale:.2f} "
                    f"{seg.end_point.x / scale:.2f} {seg.end_point.y / scale:.2f}"
                )
        segs.append("Z")
        parts.append(" ".join(segs))
    return " ".join(parts)


def trace_bitmap(mask: np.ndarray) -> str:
    side = mask.shape[0]
    scale = side / 100
    bmp = Bitmap(mask)
    path = bmp.trace(
        turdsize=18,
        turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
        alphamax=0.9,
        opticurve=True,
        opttolerance=0.2,
    )
    return curves_to_d(path, scale, side)


def svg_mark(navy_d: str, orange_d: str, *, navy: str, accent: str, label: str) -> str:
    # When mono, merge orange into navy fill
    if accent == navy:
        d = f"{navy_d} {orange_d}".strip()
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="{label}">
  <title>{label}</title>
  <path fill="{navy}" fill-rule="evenodd" d="{d}"/>
</svg>
'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="{label}">
  <title>{label}</title>
  <path fill="{navy}" fill-rule="evenodd" d="{navy_d}"/>
  <path fill="{accent}" fill-rule="evenodd" d="{orange_d}"/>
</svg>
'''


def extract_inner(svg: str) -> str:
    start = svg.find(">", svg.find("<svg")) + 1
    end = svg.rfind("</svg>")
    body = svg[start:end]
    if "<title>" in body:
        t0 = body.find("<title>")
        t1 = body.find("</title>") + len("</title>")
        body = body[:t0] + body[t1:]
    return body.strip()


def lockup_h(inner: str, fill: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 100" role="img" aria-label="Allround Systems lockup horizontal">
  <title>Allround Systems lockup horizontal</title>
  <g transform="translate(2 2) scale(0.96)">{inner}</g>
  <g fill="{fill}" font-family="Montserrat, Arial Narrow, Arial, Helvetica, sans-serif" font-weight="700" letter-spacing="0.18em">
    <text x="118" y="42" font-size="22">ALLROUND</text>
    <text x="118" y="72" font-size="22">SYSTEMS</text>
  </g>
</svg>
'''


def lockup_s(inner: str, fill: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 210" role="img" aria-label="Allround Systems lockup stacked">
  <title>Allround Systems lockup stacked</title>
  <g transform="translate(50 4)">{inner}</g>
  <g fill="{fill}" font-family="Montserrat, Arial Narrow, Arial, Helvetica, sans-serif" font-weight="700" letter-spacing="0.2em" text-anchor="middle">
    <text x="100" y="138" font-size="14">ALLROUND</text>
    <text x="100" y="162" font-size="14">SYSTEMS</text>
  </g>
</svg>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ink, orange = load_mark_bitmap()
    # Preview bins
    Image.fromarray((~ink).astype(np.uint8) * 255).save(ROOT / "variants" / "_final-mark-bin.png")
    Image.fromarray((~orange).astype(np.uint8) * 255).save(ROOT / "variants" / "_final-orange-bin.png")

    # Navy-only = ink minus orange tip (so tip can be recolored)
    navy_mask = ink & ~orange
    # Keep a little connectivity: if orange empty, use full ink
    if orange.sum() < 30:
        navy_mask = ink
        orange_d = ""
        navy_d = trace_bitmap(navy_mask)
    else:
        navy_d = trace_bitmap(navy_mask)
        orange_d = trace_bitmap(orange)

    variants = {
        "as-mark.svg": (NAVY, ORANGE, "Allround Systems mark"),
        "as-mark-color.svg": (NAVY, ORANGE, "Allround Systems mark — color"),
        "as-mark-mono.svg": (NAVY, NAVY, "Allround Systems mark — mono"),
        "as-mark-black.svg": (BLACK, BLACK, "Allround Systems mark — black"),
        "as-mark-white.svg": (WHITE, WHITE, "Allround Systems mark — white"),
        "as-mark-reversed.svg": (PAPER, ORANGE, "Allround Systems mark — reversed"),
        "as-mark-on-signal.svg": (NAVY, PAPER, "Allround Systems mark — on signal"),
        "as-mark-traced.svg": (NAVY, ORANGE, "Allround Systems mark — traced"),
    }

    color_svg = ""
    for name, (navy, accent, label) in variants.items():
        svg = svg_mark(navy_d, orange_d, navy=navy, accent=accent, label=label)
        (OUT / name).write_text(svg, encoding="utf-8")
        print("wrote", name)
        if name == "as-mark-color.svg":
            color_svg = svg

    inner = extract_inner(color_svg)
    inner_rev = extract_inner(svg_mark(navy_d, orange_d, navy=PAPER, accent=ORANGE, label="rev"))
    (OUT / "as-lockup-horizontal-light.svg").write_text(lockup_h(inner, NAVY), encoding="utf-8")
    (OUT / "as-lockup-horizontal-dark.svg").write_text(lockup_h(inner_rev, PAPER), encoding="utf-8")
    (OUT / "as-lockup-stacked-light.svg").write_text(lockup_s(inner, NAVY), encoding="utf-8")

    app = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="Allround Systems app icon">
  <title>Allround Systems app icon</title>
  <rect width="100" height="100" rx="22" fill="{NAVY}"/>
  <g transform="translate(8 8) scale(0.84)">{extract_inner(svg_mark(navy_d, orange_d, navy=PAPER, accent=ORANGE, label="i"))}</g>
</svg>
'''
    (OUT / "as-app-icon.svg").write_text(app, encoding="utf-8")
    fav = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Allround Systems favicon">
  <title>Allround Systems favicon</title>
  <g transform="scale(0.32)">{inner}</g>
</svg>
'''
    (OUT / "as-favicon.svg").write_text(fav, encoding="utf-8")

    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "brand-mark-black.svg").write_text(
        svg_mark(navy_d, orange_d, navy=BLACK, accent=BLACK, label="Allround Systems mark — black"),
        encoding="utf-8",
    )
    (PUBLIC / "brand-app-icon.svg").write_text(app, encoding="utf-8")
    (PUBLIC / "icon.svg").write_text(fav, encoding="utf-8")
    (PUBLIC / "logo.svg").write_text(lockup_h(inner, NAVY), encoding="utf-8")
    print("public mirrors updated")


if __name__ == "__main__":
    main()
