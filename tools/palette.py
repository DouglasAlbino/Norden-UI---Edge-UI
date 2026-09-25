r"""The colour rule shared by every tool here: Norden UI's neutrals -> Edge UI's neutrals.

Norden UI is built on a neutral grey ramp (panel #333333 = 51, headers/hover/dividers above it,
near-black below). Edge UI uses the same kind of ramp, only darker at the bottom and cleaner at the
top. So the recolour is a ramp-to-ramp remap, not a single darkening formula:

  * a colour node counts as NEUTRAL when its channel spread (max - min) is <= `neutral_spread`;
    those are the greys Norden builds its panels out of, and only those are remapped.
  * a neutral's value v is mapped through `neutral_ramp`, a piecewise-linear curve from Norden's
    anchors to Edge's. The curve is monotone, so the order of Norden's greys - panel darker than
    header darker than divider - survives; hover states and borders stay distinct instead of
    collapsing into one flat block.
  * hued colours (Norden's slate blue-greys, icon tints, the red/green/gold status colours) are left
    untouched by default. `accent_enabled` (or --accents) additionally pulls saturated colours onto
    Edge's accent hue while keeping their own brightness - off by default, because Edge itself keeps
    Skyrim's status colours.
  * alpha is never read and never written. Every fade, every opacity, is Norden's own.

Anchors live in palette/edge-ui.json. If palette/edge-ui.measured.json exists (written by
sample-edge.py from a real Edge UI install) it wins, so the shipped defaults are only a fallback.

    python palette.py              print the mapping table
    python palette.py --selftest   check the invariants (monotone, endpoints, alpha, hues)
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PALETTE_DIR = os.path.join(ROOT, "palette")
DEFAULT = os.path.join(PALETTE_DIR, "edge-ui.json")
MEASURED = os.path.join(PALETTE_DIR, "edge-ui.measured.json")


def load(path=None):
    """Measured palette if present, else the shipped default, else an explicit path."""
    p = path or (MEASURED if os.path.exists(MEASURED) else DEFAULT)
    with open(p, encoding="utf-8-sig") as fh:
        pal = json.load(fh)
    pal["_path"] = p
    pal["neutral_ramp"] = sorted((int(a), int(b)) for a, b in pal["neutral_ramp"])
    return pal


def _interp(v, ramp):
    v = max(0, min(255, int(v)))
    if v <= ramp[0][0]:
        return ramp[0][1]
    for (x0, y0), (x1, y1) in zip(ramp, ramp[1:]):
        if v <= x1:
            if x1 == x0:
                return y1
            return int(round(y0 + (y1 - y0) * (v - x0) / (x1 - x0)))
    return ramp[-1][1]


def _hexk(rgb):
    return "%02x%02x%02x" % tuple(rgb)


def is_protected(rgb, pal):
    """Mask / colour-transform placeholders. Edge and Norden both paint #00ff00 and #00ffff into
    shapes that Scaleform replaces at run time (730 nodes across 172 Norden files); recolouring one
    breaks the effect, so they are never touched."""
    return _hexk(rgb) in {h.lower() for h in pal.get("protected", [])}


def is_neutral(rgb, pal):
    return max(rgb) - min(rgb) <= int(pal.get("neutral_spread", 3))


def _sat(rgb):
    return max(rgb) - min(rgb)


def map_rgb(rgb, pal, accents=None):
    """Norden colour -> Edge colour. Returns the same tuple when nothing applies."""
    r, g, b = (int(c) for c in rgb)
    if is_protected((r, g, b), pal):
        return (r, g, b)
    explicit = {k.lower(): v for k, v in pal.get("accent_map", {}).items()}
    if _hexk((r, g, b)) in explicit:
        h = explicit[_hexk((r, g, b))]
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    if is_neutral((r, g, b), pal):
        v = _interp(round((r + g + b) / 3), pal["neutral_ramp"])
        return (v, v, v)
    use_accent = pal.get("accent_enabled", False) if accents is None else accents
    if use_accent and _sat((r, g, b)) >= int(pal.get("accent_min_saturation", 12)):
        ar, ag, ab = pal["accent"]
        luma = _interp(round(0.2126 * r + 0.7152 * g + 0.0722 * b), pal.get("accent_luma_ramp", [[0, 0], [255, 255]]))
        an = max(1, round(0.2126 * ar + 0.7152 * ag + 0.0722 * ab))
        k = luma / an
        return tuple(max(0, min(255, round(c * k))) for c in (ar, ag, ab))
    return (r, g, b)


def table(pal):
    rows = []
    for v in (0, 13, 26, 34, 51, 64, 77, 88, 102, 128, 160, 192, 208, 224, 235, 255):
        rows.append((v, _interp(v, pal["neutral_ramp"])))
    return rows


def _selftest(pal):
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and cond

    ys = [_interp(v, pal["neutral_ramp"]) for v in range(256)]
    check(all(y1 >= y0 for y0, y1 in zip(ys, ys[1:])), "ramp is monotone (grey order preserved)")
    check(ys[0] == 0 and ys[255] == 255, "black stays black, white stays white")
    check(ys[51] < ys[64] < ys[88] < ys[102], "panel < header < hover < divider stay distinct")
    check(ys[51] <= 51, "Norden's #333333 panel is not lightened")
    check(map_rgb((91, 103, 109), pal) == (91, 103, 109), "hued slate #5b676d untouched")
    check(map_rgb((200, 60, 60), pal) == (200, 60, 60), "status red untouched")
    check(map_rgb((0, 255, 0), pal) == (0, 255, 0), "mask #00ff00 protected")
    check(map_rgb((0, 255, 255), pal) == (0, 255, 255), "mask #00ffff protected")
    check(map_rgb((0, 50, 170), pal) == (0, 50, 170), "colour shared with Edge untouched")
    if pal.get("accent_map"):
        check(map_rgb((255, 215, 0), pal) == (245, 216, 124), "Norden gold #ffd700 -> Edge #f5d87c")
    check(map_rgb((0, 255, 0), pal, accents=True) == (0, 255, 0), "mask still protected with --accents")
    check(map_rgb((52, 51, 50), pal) == (ys[51],) * 3, "near-neutral within spread is remapped")
    check(map_rgb((51, 51, 61), pal) == (51, 51, 61), "outside the spread is left alone")
    a = map_rgb((91, 103, 190), pal, accents=True)
    check(_sat(a) > 0 and a != (91, 103, 190), "--accents moves a hued colour onto the Edge accent")
    return ok


if __name__ == "__main__":
    pal = load()
    print(f"palette: {pal['name']}  ({os.path.relpath(pal['_path'], ROOT)})")
    print("  Norden -> Edge")
    for v, y in table(pal):
        print(f"  {v:3d} (#{v:02x}{v:02x}{v:02x}) -> {y:3d} (#{y:02x}{y:02x}{y:02x})")
    if "--selftest" in sys.argv:
        print("selftest:")
        sys.exit(0 if _selftest(pal) else 1)
