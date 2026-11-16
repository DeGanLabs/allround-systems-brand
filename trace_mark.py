"""
Build Allround Systems mark SVGs:
  - AS monogram: pixel-traced from _source-mark.png (potrace)
  - Ring: perfect geometric circle with 8 equal gaps
"""
from __future__ import annotations

import math
import re
import shutil
from pathlib import Path

import numpy as np
import potrace
from PIL import Image
from potrace import Bitmap

NAVY = "#0B243B"
ORANGE = "#F19E38"
PAPER = "#F5F3ED"
BLACK = "#000000"
WHITE = "#FFFFFF"

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "svg"
PUBLIC = ROOT.parent / "public"

# Ring construction (viewBox 0 0 100 100)
CX = CY = 50.0
RING_R = 42.0
RING_SW = 7.4
GAP_DEG = 7.0  # missing arc between segments
N_SEGS = 8
# Accent = top-right (~1 o'clock). In SVG y-down, CW-from-east: north=270, 1 o'clock ≈ 292.5 → segment index 6
ACCENT_INDEX = 6


def load_clean_square() -> np.ndarray:
    im = Image.open(ROOT / "_source-mark.png").convert("RGBA")
    a = np.array(im)
    ink = (a[:, :, :3].mean(axis=2) < 60) & (a[:, :, 3] > 200)
    h, w = ink.shape
    clean = ink.copy()
    for x in range(w):
        if clean[:, x].sum() < 40:
            clean[:, x] = False
    for y in range(h):
        if clean[y, :].sum() < 40:
            clean[y, :] = False
    ys, xs = np.where(clean)
    crop = clean[int(ys.min()) : int(ys.max()) + 1, int(xs.min()) : int(xs.max()) + 1]
    ch, cw = crop.shape
    pad = 48
    side = max(ch, cw) + pad * 2
    sq = np.zeros((side, side), dtype=bool)
    oy = (side - ch) // 2
    ox = (side - cw) // 2
    sq[oy : oy + ch, ox : ox + cw] = crop
    return sq


def curve_to_d(curve: potrace.Curve, scale: int) -> str:
    sp = curve.start_point
    parts = [f"M{sp.x / scale:.3f} {sp.y / scale:.3f}"]
    for seg in curve.segments:
        if seg.is_corner:
            parts.append(
                f"L{seg.c.x / scale:.3f} {seg.c.y / scale:.3f} "
                f"L{seg.end_point.x / scale:.3f} {seg.end_point.y / scale:.3f}"
            )
        else:
            parts.append(
                f"C{seg.c1.x / scale:.3f} {seg.c1.y / scale:.3f} "
                f"{seg.c2.x / scale:.3f} {seg.c2.y / scale:.3f} "
                f"{seg.end_point.x / scale:.3f} {seg.end_point.y / scale:.3f}"
            )
    parts.append("Z")
    return " ".join(parts)


def path_bbox(d: str) -> tuple[float, float, float, float]:
    nums = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", d)]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def normalize_to_box(
    d: str,
    target: tuple[float, float, float, float],
) -> str:
    """Map path bbox into target (x,y,w,h) box, preserving aspect, centered."""
    minx, miny, maxx, maxy = path_bbox(d)
    bw, bh = maxx - minx, maxy - miny
    tx, ty, tw, th = target
    sc = min(tw / bw, th / bh)
    ox = tx + (tw - bw * sc) / 2 - minx * sc
    oy = ty + (th - bh * sc) / 2 - miny * sc
    tokens = re.findall(r"[MLCZ]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    out: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        out.append(t)
        i += 1
        if t == "Z":
            continue
        n = 6 if t == "C" else 2
        coords = [float(tokens[i + k]) for k in range(n)]
        i += n
        for j in range(0, len(coords), 2):
            out.append(f"{coords[j] * sc + ox:.3f}")
            out.append(f"{coords[j + 1] * sc + oy:.3f}")
    return " ".join(out)


def extract_monogram(sq: np.ndarray) -> str:
    """Potrace only the AS (mask out ring), return raw path in square coords."""
    side = sq.shape[0]
    cy = cx = (side - 1) / 2.0
    yy, xx = np.mgrid[0:side, 0:side]
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    r_out = float(rr[sq].max())
    band = sq & (rr > r_out * 0.78)
    r_inner = float(rr[band].min())
    # Keep only interior monogram ink
    mono = sq & (rr < r_inner - 3)
    Image.fromarray((~mono * 255).astype(np.uint8)).save(ROOT / "_mono-only.png")

    scale = 4
    big = np.repeat(np.repeat(mono, scale, axis=0), scale, axis=1)
    path = Bitmap(big).trace(
        turdsize=20,
        turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
        alphamax=0.0,
        opticurve=True,
        opttolerance=0.1,
    )
    chunks: list[str] = []
    for curve in path:
        d = curve_to_d(curve, scale)
        minx, miny, maxx, maxy = path_bbox(d)
        area = (maxx - minx) * (maxy - miny)
        if area < 50:
            continue
        # Drop full-frame ghost (potrace outer path) — AS must be positive fill, not a hole
        full = area > (side * side * 0.5)
        touches = minx <= 1 or miny <= 1 or maxx >= side - 1 or maxy >= side - 1
        if full or (touches and area > side * side * 0.25):
            print(f"drop mono frame area={area:.0f}")
            continue
        chunks.append(d)
    if not chunks:
        raise RuntimeError("no monogram path traced")
    print(f"monogram components: {len(chunks)}")
    return " ".join(chunks)


def ring_arcs(ma: str, mb: str) -> str:
    """Perfect circle broken into N equal gaps; one accent segment."""
    seg_deg = 360.0 / N_SEGS - GAP_DEG
    lines: list[str] = []
    for i in range(N_SEGS):
        start = i * (360.0 / N_SEGS) + GAP_DEG / 2
        end = start + seg_deg
        # CW from east in y-down SVG
        th1 = math.radians(start)
        th2 = math.radians(end)
        x1 = CX + RING_R * math.cos(th1)
        y1 = CY + RING_R * math.sin(th1)
        x2 = CX + RING_R * math.cos(th2)
        y2 = CY + RING_R * math.sin(th2)
        color = mb if i == ACCENT_INDEX else ma
        lines.append(
            f'<path d="M{x1:.3f} {y1:.3f} A{RING_R} {RING_R} 0 0 1 {x2:.3f} {y2:.3f}" '
            f'stroke="{color}" stroke-width="{RING_SW}" stroke-linecap="butt" fill="none"/>'
        )
    return "\n  ".join(lines)


def mark_body(mono_d: str, ma: str, mb: str) -> str:
    return f"""  {ring_arcs(ma, mb)}
  <path fill="{ma}" fill-rule="evenodd" d="{mono_d}"/>"""


def svg_doc(body: str, title: str, vb: str = "0 0 100 100") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="{title}">
  <title>{title}</title>
{body}
</svg>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sq = load_clean_square()
    Image.fromarray((~sq * 255).astype(np.uint8)).save(ROOT / "_traced-input.png")

    raw_mono = extract_monogram(sq)
    # Fit AS inside the ring with breathing room (inner radius ≈ 42 - 7.4/2 = 38.3)
    inner = RING_R - RING_SW / 2 - 2.5
    mono = normalize_to_box(raw_mono, (50 - inner, 50 - inner * 0.72, inner * 2, inner * 1.44))
    # AS sits a bit high in the source — nudge up slightly by remapping with vertical bias
    # Re-fit with a box matching source proportions (wider than tall)
    mono = normalize_to_box(raw_mono, (28.5, 27.5, 43.0, 33.0))

    variants = {
        "as-mark-color.svg": (NAVY, ORANGE, "Allround Systems mark — color"),
        "as-mark-mono.svg": (NAVY, NAVY, "Allround Systems mark — mono"),
        "as-mark-black.svg": (BLACK, BLACK, "Allround Systems mark — black"),
        "as-mark-white.svg": (WHITE, WHITE, "Allround Systems mark — white"),
        "as-mark-reversed.svg": (WHITE, ORANGE, "Allround Systems mark — reversed"),
        "as-mark-on-signal.svg": (NAVY, PAPER, "Allround Systems mark — on signal"),
        "as-favicon.svg": (NAVY, ORANGE, "Allround Systems favicon"),
        "as-mark-traced.svg": (BLACK, BLACK, "Allround Systems mark — traced"),
    }
    for name, (ma, mb, title) in variants.items():
        (OUT / name).write_text(svg_doc(mark_body(mono, ma, mb), title), encoding="utf-8")

    (OUT / "as-mark.svg").write_text((OUT / "as-mark-color.svg").read_text(encoding="utf-8"), encoding="utf-8")

    app = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="Allround Systems app icon">
  <title>Allround Systems app icon</title>
  <rect width="100" height="100" rx="22" fill="{NAVY}"/>
  <g transform="translate(18 18) scale(0.64)">
{mark_body(mono, WHITE, ORANGE)}
  </g>
</svg>
"""
    (OUT / "as-app-icon.svg").write_text(app, encoding="utf-8")

    for name, ma, text, mb in [
        ("as-lockup-horizontal-light.svg", NAVY, NAVY, ORANGE),
        ("as-lockup-horizontal-dark.svg", WHITE, WHITE, ORANGE),
    ]:
        body = f"""{mark_body(mono, ma, mb)}
  <g fill="{text}" font-family="Inter, Montserrat, Arial, Helvetica, sans-serif" font-weight="700">
    <text x="118" y="44" font-size="28" letter-spacing="0.14em">ALLROUND</text>
    <text x="118" y="76" font-size="28" letter-spacing="0.14em">SYSTEMS</text>
  </g>"""
        (OUT / name).write_text(svg_doc(body, name, "0 0 420 100"), encoding="utf-8")

    stacked = f"""  <g transform="translate(60 6)">
{mark_body(mono, NAVY, ORANGE)}
  </g>
  <g fill="{NAVY}" font-family="Inter, Montserrat, Arial, Helvetica, sans-serif" font-weight="700" text-anchor="middle">
    <text x="110" y="138" font-size="22" letter-spacing="0.16em">ALLROUND</text>
    <text x="110" y="166" font-size="22" letter-spacing="0.16em">SYSTEMS</text>
  </g>"""
    (OUT / "as-lockup-stacked-light.svg").write_text(
        svg_doc(stacked, "Allround Systems lockup — stacked", "0 0 220 190"), encoding="utf-8"
    )

    (ROOT / "compare.html").write_text(
        """<!doctype html>
<html><head><meta charset="utf-8"><title>AS + geometric ring</title>
<style>
  body{margin:0;font-family:Inter,system-ui,sans-serif;background:#f5f3ed;padding:28px;color:#0B243B}
  .row{display:flex;gap:20px;flex-wrap:wrap}
  .card{background:#fff;border:1px solid #ddd;border-radius:12px;padding:18px;text-align:center}
  img{width:220px;height:220px;object-fit:contain}
  h1{font-size:18px;margin:0 0 16px}
</style></head><body>
<h1>Traced AS + perfect circle ring</h1>
<div class="row">
  <div class="card"><img src="_source-mark.png" alt=""><p>Source PNG</p></div>
  <div class="card"><img src="_mono-only.png" alt=""><p>AS only (traced)</p></div>
  <div class="card"><img src="svg/as-mark-black.svg" alt=""><p>Final mark</p></div>
  <div class="card" style="background:#0B243B"><img src="svg/as-mark-reversed.svg" alt=""><p style="color:#fff">Reversed + Signal</p></div>
</div>
</body></html>
""",
        encoding="utf-8",
    )

    PUBLIC.mkdir(parents=True, exist_ok=True)
    shutil.copy(OUT / "as-favicon.svg", PUBLIC / "icon.svg")
    shutil.copy(OUT / "as-mark-color.svg", PUBLIC / "logo.svg")
    shutil.copy(OUT / "as-app-icon.svg", PUBLIC / "brand-app-icon.svg")
    shutil.copy(OUT / "as-mark-black.svg", PUBLIC / "brand-mark-black.svg")
    print("OK — traced AS + geometric ring")


if __name__ == "__main__":
    main()
