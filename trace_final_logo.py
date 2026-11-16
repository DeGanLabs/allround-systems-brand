"""Pixel-faithful trace of the approved final logo into SVG masters + PNG masters."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import potrace
from PIL import Image
from potrace import Bitmap

ROOT = Path(__file__).resolve().parent
SRC_PNG = ROOT / "variants" / "_source-final-logo.png"
SRC_JPG = ROOT / "variants" / "_source-final-logo.jpg"
OUT = ROOT / "svg"
PUBLIC = ROOT.parent / "public"
VAR = ROOT / "variants"

NAVY = "#0B243B"
ORANGE = "#F19E38"
PAPER = "#F5F3ED"
BLACK = "#000000"
WHITE = "#FFFFFF"
NAVY_RGB = (11, 36, 59)
ORANGE_RGB = (241, 158, 56)
PAPER_RGB = (245, 243, 237)


def load_source() -> Image.Image:
    path = SRC_PNG if SRC_PNG.exists() else SRC_JPG
    return Image.open(path).convert("RGB")


def color_masks(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Separate navy ink and signal tip from paper background."""
    dark = rgb.mean(axis=2) < 90
    orange = (
        (rgb[:, :, 0] > 170)
        & (rgb[:, :, 1] < 175)
        & (rgb[:, :, 2] < 130)
        & (rgb[:, :, 0] > rgb[:, :, 1] + 15)
    )
    return dark, orange


def ink_bbox(ink: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(ink)
    return int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1


def find_mark_cut(full: np.ndarray) -> int:
    """Split mark (top) from wordmark (bottom) at the empty gap."""
    dens = full.sum(axis=1)
    half = len(dens) // 2
    for i in range(half, len(dens)):
        if dens[i] < full.shape[1] * 0.015:
            return i
    return int(len(dens) * 0.72)


def pad_square(mask: np.ndarray, pad: int = 28) -> np.ndarray:
    h, w = mask.shape
    side = max(h, w) + pad * 2
    sq = np.zeros((side, side), dtype=bool)
    oy, ox = (side - h) // 2, (side - w) // 2
    sq[oy : oy + h, ox : ox + w] = mask
    return sq


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


def touches_border(curve: potrace.Curve, side: int, margin: float = 1.5) -> bool:
    return any(
        x <= margin or y <= margin or x >= side - margin or y >= side - margin
        for x, y in curve_points(curve)
    )


def curves_to_d(path: potrace.Path, scale: float, side: int) -> str:
    parts: list[str] = []
    for curve in path:
        if touches_border(curve, side):
            continue
        sp = curve.start_point
        segs = [f"M{sp.x / scale:.3f} {sp.y / scale:.3f}"]
        for seg in curve.segments:
            if seg.is_corner:
                segs.append(
                    f"L{seg.c.x / scale:.3f} {seg.c.y / scale:.3f} "
                    f"L{seg.end_point.x / scale:.3f} {seg.end_point.y / scale:.3f}"
                )
            else:
                segs.append(
                    f"C{seg.c1.x / scale:.3f} {seg.c1.y / scale:.3f} "
                    f"{seg.c2.x / scale:.3f} {seg.c2.y / scale:.3f} "
                    f"{seg.end_point.x / scale:.3f} {seg.end_point.y / scale:.3f}"
                )
        segs.append("Z")
        parts.append(" ".join(segs))
    return " ".join(parts)


def trace_bitmap(mask: np.ndarray) -> str:
    """High-fidelity / pixel-faithful potrace."""
    side = mask.shape[0]
    scale = side / 100.0
    bmp = Bitmap(mask)
    path = bmp.trace(
        turdsize=4,
        turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
        alphamax=1.0,
        opticurve=True,
        opttolerance=0.12,
    )
    return curves_to_d(path, scale, side)


def svg_mark(navy_d: str, orange_d: str, *, navy: str, accent: str, label: str) -> str:
    if accent == navy or not orange_d:
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


def paint_rgba(navy_m: np.ndarray, orange_m: np.ndarray) -> Image.Image:
    h, w = navy_m.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[navy_m] = (*NAVY_RGB, 255)
    rgba[orange_m] = (*ORANGE_RGB, 255)
    return Image.fromarray(rgba, "RGBA")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    VAR.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)

    src = load_source()
    rgb = np.array(src)
    dark, orange = color_masks(rgb)
    ink = dark | orange
    y0, y1, x0, x1 = ink_bbox(ink)
    full = ink[y0:y1, x0:x1]
    orange_c = orange[y0:y1, x0:x1]
    cut = find_mark_cut(full)

    mark = full[:cut]
    omark = orange_c[:cut]
    navy_m = mark & ~omark

    # Full logo crop (mark + wordmark) — exact pixel master
    full_navy = (dark & ~orange)[y0:y1, x0:x1]
    full_orange = orange[y0:y1, x0:x1]
    paint_rgba(full_navy, full_orange).save(VAR / "as-lockup-stacked-exact.png")
    paint_rgba(navy_m, omark).save(VAR / "as-mark-exact.png")

    # Binary previews
    Image.fromarray((~pad_square(navy_m | omark)).astype(np.uint8) * 255).save(VAR / "_final-mark-bin.png")
    Image.fromarray((~pad_square(omark)).astype(np.uint8) * 255).save(VAR / "_final-orange-bin.png")

    sq_n = pad_square(navy_m)
    sq_o = pad_square(omark)
    navy_d = trace_bitmap(sq_n)
    orange_d = trace_bitmap(sq_o) if omark.sum() > 20 else ""

    # Also trace full stacked lockup (mark + wordmark) as one SVG
    sq_full_n = pad_square(full_navy, pad=40)
    # taller canvas for wordmark
    fh, fw = full_navy.shape
    side_h = int(max(fh, fw) * 1.08) + 80
    side_w = int(max(fh, fw) * 1.08) + 80
    # keep aspect of full lockup
    canvas_n = np.zeros((side_h, side_w), dtype=bool)
    canvas_o = np.zeros((side_h, side_w), dtype=bool)
    oy = (side_h - fh) // 2
    ox = (side_w - fw) // 2
    canvas_n[oy : oy + fh, ox : ox + fw] = full_navy
    canvas_o[oy : oy + fh, ox : ox + fw] = full_orange
    # viewBox matching aspect
    aspect_w = 100
    aspect_h = 100 * side_h / side_w
    scale_full = side_w / 100.0

    def trace_to_d(mask: np.ndarray, scale: float) -> str:
        side = max(mask.shape)
        bmp = Bitmap(mask)
        path = bmp.trace(
            turdsize=4,
            turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
            alphamax=1.0,
            opticurve=True,
            opttolerance=0.12,
        )
        return curves_to_d(path, scale, mask.shape[1] if mask.shape[1] >= mask.shape[0] else mask.shape[0])

    # For full lockup, scale by width
    full_navy_d = curves_to_d(
        Bitmap(canvas_n).trace(
            turdsize=4,
            turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
            alphamax=1.0,
            opticurve=True,
            opttolerance=0.12,
        ),
        scale_full,
        max(side_h, side_w),
    )
    full_orange_d = curves_to_d(
        Bitmap(canvas_o).trace(
            turdsize=2,
            turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
            alphamax=1.0,
            opticurve=True,
            opttolerance=0.12,
        ),
        scale_full,
        max(side_h, side_w),
    )
    stacked_exact = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {aspect_w:.2f} {aspect_h:.2f}" role="img" aria-label="Allround Systems lockup stacked — traced">
  <title>Allround Systems lockup stacked — traced</title>
  <path fill="{NAVY}" fill-rule="evenodd" d="{full_navy_d}"/>
  <path fill="{ORANGE}" fill-rule="evenodd" d="{full_orange_d}"/>
</svg>
'''
    (OUT / "as-lockup-stacked-traced.svg").write_text(stacked_exact, encoding="utf-8")
    print("wrote as-lockup-stacked-traced.svg")

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

    (PUBLIC / "brand-mark-black.svg").write_text(
        svg_mark(navy_d, orange_d, navy=BLACK, accent=BLACK, label="Allround Systems mark — black"),
        encoding="utf-8",
    )
    (PUBLIC / "brand-app-icon.svg").write_text(app, encoding="utf-8")
    (PUBLIC / "icon.svg").write_text(fav, encoding="utf-8")
    (PUBLIC / "logo.svg").write_text(lockup_h(inner, NAVY), encoding="utf-8")
    paint_rgba(navy_m, omark).save(PUBLIC / "brand-mark.png")
    paint_rgba(full_navy, full_orange).save(PUBLIC / "brand-lockup-stacked.png")
    print("public mirrors updated")


if __name__ == "__main__":
    main()
