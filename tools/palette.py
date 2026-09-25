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
import json, os, sys, colorsys

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


# ---------------------------------------------------------------- colour-temperature transfer
#
# 1.0.0 mapped the neutral ramp and left every hue alone. Measured, that was defensible - the two
# mods share most of their ramp - but installed it read as Norden, because what makes Edge look like
# Edge is not its greys: 35% of Edge's text nodes are cream or gold (#ece2b7, #f5d87c, #aaa07a)
# against 5% of Norden's, concentrated in the quest journal, HUD, stats, inventory and start menu.
#
# So: Edge's colour temperature, Norden's structure. For a node in Norden's quest_journal.swf, look
# at what Edge paints in the SAME role in ITS quest_journal.swf and adopt the hue and saturation at
# Norden's own luminance. Nothing is snapped, so gradients, contrast and grey order survive.

ROLES_PATH = os.path.join(PALETTE_DIR, "edge-roles.json")
_roles_cache = {}
_chroma_cache = {}


def load_roles(path=ROLES_PATH):
    if path not in _roles_cache:
        with open(path, encoding="utf-8-sig") as fh:
            d = json.load(fh)
        conv = lambda tbl: {r: [(tuple(k), c) for k, c in v] for r, v in tbl.items()}
        _roles_cache[path] = {"global": conv(d["global"]),
                              "files": {f: conv(v) for f, v in d["files"].items()}}
    return _roles_cache[path]


def _luma(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _sat_of(rgb):
    return max(rgb) - min(rgb)


def tint(value, chroma, max_sat=0.35):
    """Norden's luminance wearing Edge's hue and saturation.

    Saturation is capped: Edge's everyday cream #ece2b7 is only 22% saturated, and letting a rare
    fully saturated gold set the tone paints whole menus in it. And HSV's V is not luminance, so the
    result is rescaled back to the luminance asked for - otherwise warm text comes out darker than
    the text it replaced and the UI quietly loses contrast.
    """
    h, s_ref = chroma
    s_ref = min(s_ref, max_sat)
    v = max(0.0, min(1.0, value / 255))
    r, g, b = colorsys.hsv_to_rgb(h, s_ref, v)
    out = [c * 255 for c in (r, g, b)]
    got = _luma(out)
    if got > 0.5:
        out = [min(255.0, c * (value / got)) for c in out]
        if max(out) >= 255.0 and _luma(out) < value - 1:
            lift = value - _luma(out)
            out = [min(255.0, c + lift) for c in out]
    return tuple(int(round(c)) for c in out)


def warm_profile(role, basename, pal=None):
    """How warm Edge paints this role in this menu, and with what chroma.

    Per menu and role, Edge's warm entries are 5-28% of the nodes and always sit next to plain white
    (quest_journal is 23% #f5d87c and 15% #ece2b7 but still 26% white). So the question is not "which
    single Edge colour is nearest" - that picks white and changes nothing, or picks a rare gold and
    washes the menu - but "does Edge run warm here, and how warm".

    Only the cream-gold band counts: hue 25-65 degrees, saturation 12-60%. Skyrim's status reds
    (#9d0000, #803300, #280c02) are warm too and are inherited from vanilla by BOTH mods; averaging
    them in turned cream text pink (#cccccc -> #ffbfb3 across 532 nodes) on the first attempt.
    """
    key = (role, (basename or "").lower())
    if key in _chroma_cache:
        return _chroma_cache[key]
    roles = load_roles()
    table = roles["files"].get(key[1], {}).get(role) or roles["global"].get(role) or []
    total = sum(w for _, w in table) or 1
    lo, hi = 25 / 360.0, 65 / 360.0
    warm = []
    for k, w in table:
        if not (40 <= max(k) <= 250):
            continue
        h, _, sat = colorsys.rgb_to_hsv(*[c / 255 for c in k])
        if lo <= h <= hi and 0.12 <= sat <= 0.60:
            warm.append((k, w))
    if not warm:
        _chroma_cache[key] = (0.0, None)
        return _chroma_cache[key]
    share = sum(w for _, w in warm) / total
    tw = sum(w for _, w in warm)
    hs = ss = 0.0
    for k, w in warm:
        h, _, sat = colorsys.rgb_to_hsv(*[c / 255 for c in k])
        hs += h * w
        ss += sat * w
    _chroma_cache[key] = (share, (hs / tw, ss / tw))
    return _chroma_cache[key]


# ---------------------------------------------------------------- rendered-pixel matching
#
# The node census cannot see screen area, so it read the mid greys as shared and every ramp came out
# as identity through 128-204 - which is why the menu bodies never moved. Rendered and measured per
# menu (tools/render-census.py) the picture is different, and it holds a surprise: across the 131
# menus both mods draw, the MEDIAN luminance gap is 1 of 255. The bodies already match. The outliers
# are real though, and run both ways - statsmenu 140 vs 48, craftingmenu 163 vs 90, but
# trainingmenu_fill 101 vs 220 - so this fits one monotone curve per menu, only where warranted.

RENDER_PATH = os.path.join(PALETTE_DIR, "render-census.json")
_render_cache = {}
_curve_cache = {}


def load_render(path=RENDER_PATH):
    if path not in _render_cache:
        if not os.path.exists(path):
            _render_cache[path] = None
        else:
            with open(path, encoding="utf-8-sig") as fh:
                d = json.load(fh)
            _render_cache[path] = {"menus": {
                n.lower(): {t: sorted((int(k), v) for k, v in h.items()) for t, h in sides.items()}
                for n, sides in d.get("menus", {}).items()}}
    return _render_cache[path]


def _at_quantile(hist, p):
    tot = sum(w for _, w in hist)
    if not tot:
        return None
    acc = 0.0
    for l, w in hist:
        acc += w
        if acc / tot >= p:
            return float(l)
    return float(hist[-1][0])


def _menu_key(basename):
    key = (basename or "").lower()
    for suffix in (".xml", ".swf"):
        if key.endswith(suffix):
            key = key[:-4]
    return key


def render_sides(basename):
    data = load_render()
    if not data:
        return None
    key = _menu_key(basename)
    sides = data["menus"].get(key) or data["menus"].get(key + ".swf")
    return sides if sides and "norden" in sides and "edge" in sides else None


def render_curve(basename, pal):
    """A monotone luminance curve for one menu, or None for "leave this menu alone".

    None is the common answer, deliberately. The curve is skipped when the menu was not rendered on
    both sides, when the distributions already agree, and when the median gap is under
    `render_match_min_gap` - a curve fitted to a small difference is fitting noise, and one moved
    lockpickingmenu_cheat_frame from 27 to 6 against an Edge value of 33.
    """
    key = _menu_key(basename)
    if key in _curve_cache:
        return _curve_cache[key]
    sides = render_sides(basename)
    if not sides:
        _curve_cache[key] = None
        return None
    n, e = sides["norden"], sides["edge"]
    pairs = [(_at_quantile(n, i / 20.0), _at_quantile(e, i / 20.0)) for i in range(1, 20)]
    pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
    if (not pairs
            or max(abs(x - y) for x, y in pairs) <= pal.get("render_match_agree_within", 8)
            or abs(_at_quantile(n, .5) - _at_quantile(e, .5)) < pal.get("render_match_min_gap", 25)):
        _curve_cache[key] = None
        return None
    anchors, last = [], None
    for x, y in sorted(pairs):
        if last is not None and x <= last[0]:
            continue
        anchors.append((x, max(y, last[1]) if last else y))          # keep it monotone
        last = anchors[-1]
    lo, hi = _at_quantile(n, 0.02), _at_quantile(n, 0.98)
    _curve_cache[key] = (anchors, lo, hi) if len(anchors) >= 2 else None
    return _curve_cache[key]


def render_match(value, basename, pal):
    """Where Edge puts this luminance in this menu. None means "no evidence, do not move it".

    Values outside the range the render covers return None on purpose: quantile mapping pins anything
    past the ends to the extremes of the target, and in itemcard_thumb - where both mods render
    identically - that turned every dark node into 153 and shipped a menu that matched Edge exactly
    (254) at 41.
    """
    curve = render_curve(basename, pal)
    if not curve:
        return None
    anchors, lo, hi = curve
    if value < lo - 1 or value > hi + 1:
        return None
    if value <= anchors[0][0]:
        return anchors[0][1]
    if value >= anchors[-1][0]:
        return anchors[-1][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if value <= x1:
            t = 0.0 if x1 == x0 else (value - x0) / (x1 - x0)
            return y0 + (y1 - y0) * t
    return anchors[-1][1]


def transfer(rgb, pal, role, basename, strength=None):
    """Map one Norden colour by adopting Edge's temperature for that role in that menu.

    Pure white and near-black are left alone on purpose: white is still Edge's most used text colour
    and its panels are black, and anchoring both ends is what keeps this from becoming a sepia wash.
    """
    if is_protected(rgb, pal):
        return tuple(rgb)
    base = map_rgb(rgb, pal)
    if not is_neutral(rgb, pal):
        return base                                   # Norden's own status hues stay
    strength = pal.get("transfer_strength", 1.0) if strength is None else strength
    max_sat = pal.get("transfer_max_saturation", 0.35)

    # Panels, from rendered pixels - the only measurement that reflects screen area. Evidence or
    # nothing: where the renders show Norden already matches Edge the fill keeps Norden's own value,
    # because the node-census ramp was moving panels that were already right and made 43 of 130
    # menus worse. The curve is looked up with the ORIGINAL luminance - its domain is what Norden
    # renders, and feeding it the ramped value pushed menus the wrong way.
    if role in pal.get("render_match_roles", ["color"]) and load_render() is not None:
        if pal.get("render_match_evidence_only", True) and render_curve(basename, pal) is None:
            return tuple(rgb)
        src = _luma(rgb)
        q = render_match(src, basename, pal)
        if q is not None:
            a = pal.get("render_match_strength", 0.8)
            v = int(round(max(0.0, min(255.0, src * (1 - a) + q * a))))
            base = (v, v, v)
    floor = pal.get("transfer_luma_floor", 32)
    ceil = pal.get("transfer_luma_ceiling", 250)
    thresholds = pal.get("transfer_warm_share", {})
    need = thresholds.get(role, thresholds.get("default", 1.1))
    share, chroma = warm_profile(role, basename, pal)
    if chroma is None or share < need:
        return base
    l = _luma(base)
    if l < floor or l >= ceil:
        return base
    warm = tint(l, chroma, max_sat)
    if strength >= 1.0:
        return warm
    return tuple(int(round(x + (y - x) * strength)) for x, y in zip(base, warm))


def table(pal):
    rows = []
    for v in (0, 13, 26, 34, 51, 64, 77, 88, 102, 128, 160, 192, 208, 224, 235, 255):
        rows.append((v, _interp(v, pal["neutral_ramp"])))
    return rows


def _selftest(pal):
    ok = True

    def check(cond, msg, detail=""):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg + (" " + detail if detail and not cond else ""))
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
    if os.path.exists(ROLES_PATH):
        t = transfer((235, 235, 235), pal, "textColor", "quest_journal.xml")
        check(t[0] > t[2], "near-white text takes Edge's warm cast where Edge runs warm", str(t))
        check(abs(_luma(t) - _luma(map_rgb((235, 235, 235), pal))) < 12,
              "the tint keeps Norden's brightness", str(t))
        check(colorsys.rgb_to_hsv(*[x / 255 for x in t])[1] <= pal.get("transfer_max_saturation", .35) + .02,
              "saturation is capped to Edge's everyday warmth", str(t))
        check(transfer((0, 0, 0), pal, "color", "quest_journal.xml") == (0, 0, 0), "black panels stay black")
        check(transfer((0, 255, 0), pal, "color", "hudmenu.xml") == (0, 255, 0), "masks survive transfer")
        check(transfer((200, 60, 60), pal, "color", "hudmenu.xml") == (200, 60, 60),
              "Norden's status hues survive transfer")
        check(transfer((255, 255, 255), pal, "textColor", "quest_journal.xml") == (255, 255, 255),
              "pure white stays white - Edge uses plenty of it")
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
