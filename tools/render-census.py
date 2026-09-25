r"""Measure the two mods the way the player sees them: by rendering the menus and reading pixels.

Every other census here counts colour NODES in the SWF XML, and that is what let 1.0.0 and 1.1.0
leave the menu bodies untouched. A panel background is one node covering the whole screen; an icon
is two hundred nodes covering nothing. Counted by node the two mods "share" the mid greys, so every
ramp came out as identity through 128-204 and the panels never moved.

This renders frame 1 of every menu both mods have (ffdec -export frame), reads the visible pixels,
and writes each side's luminance distribution - overall and per menu - to palette/render-census.json.
`palette.render_curve()` turns a menu's pair of distributions into a correction curve.

Two artifacts have to go or the numbers mean nothing:

* **The stage background.** Both mods declare #333333 in nearly every file. Left in, it swamps the
  histogram and the two mods read as identical at every percentile. Scaleform never shows the stage
  in game - the menu is composited over the world - so those pixels are dropped. It is read straight
  from the SWF's SetBackgroundColor tag, so this tool does not need the XML export.
* **Frames too small to be a menu** (under MIN_PX visible pixels) - icons and empty shells.

    set NORDEN_UI=...  EDGE_UI=...  FFDEC=...
    python render-census.py               render and measure (existing PNGs are reused)
    python render-census.py --limit=40    fewer menus, for a quick look
"""
import os, sys, json, zlib, struct, subprocess, collections
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = os.environ.get("FFDEC", r"C:\Program Files (x86)\FFDec\ffdec-cli.exe")
NORDEN_UI = os.environ.get("NORDEN_UI", r"D:\mods\Norden UI")
EDGE_UI = os.environ.get("EDGE_UI", r"D:\mods\Edge UI")
CACHE = os.environ.get("RENDER_CACHE", os.path.join(ROOT, "build", "render"))
OUT = os.path.join(ROOT, "palette", "render-census.json")
LIMIT = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--limit=")), 0)) or None
MIN_PX = 500

try:
    from PIL import Image
except ImportError:
    sys.exit("needs Pillow: pip install pillow")


def swf_body(path):
    """Uncompressed SWF bytes after the 8-byte header, or None."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 9:
        return None
    sig = data[:3]
    if sig == b"FWS":
        return data[8:]
    if sig == b"CWS":
        try:
            return zlib.decompress(data[8:])
        except zlib.error:
            return None
    if sig == b"ZWS":                      # LZMA - rare in these mods, not worth a dependency
        return None
    return None


def stage_bg(path):
    """The SetBackgroundColor (tag 9) of a SWF, read from the binary."""
    body = swf_body(path)
    if not body:
        return None
    # skip the frame-size RECT, then frame rate (2 bytes) and frame count (2 bytes)
    nbits = body[0] >> 3
    total_bits = 5 + 4 * nbits
    pos = (total_bits + 7) // 8 + 4
    while pos + 2 <= len(body):
        (code_len,) = struct.unpack_from("<H", body, pos)
        pos += 2
        code, length = code_len >> 6, code_len & 0x3F
        if length == 0x3F:
            if pos + 4 > len(body):
                return None
            (length,) = struct.unpack_from("<I", body, pos)
            pos += 4
        if code == 9 and pos + 3 <= len(body):
            return tuple(body[pos:pos + 3])
        if code == 0:
            return None
        pos += length
    return None


def index(root, prefer=("16x9", "Interface", "interface")):
    """basename -> one representative path (prefer the 16x9 / main Interface copy)."""
    found = collections.defaultdict(list)
    for base, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".swf"):
                found[f.lower()].append(os.path.join(base, f))
    out = {}
    for name, paths in found.items():
        paths.sort(key=lambda p: (-sum(k in p for k in prefer), len(p)))
        out[name] = paths[0]
    return out


def render(job):
    tag, name, swf = job
    out = os.path.join(CACHE, tag, name[:-4])
    png = os.path.join(out, "1.png")
    if os.path.exists(png):
        return (tag, name, png, swf)
    os.makedirs(out, exist_ok=True)
    try:
        subprocess.run([FF, "-format", "frame:png", "-export", "frame", out, swf],
                       capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return None
    return (tag, name, png, swf) if os.path.exists(png) else None


def histogram(png, bg):
    im = Image.open(png).convert("RGBA")
    h = collections.Counter()
    for r, g, b, a in im.getdata():
        if a <= 8 or (bg and (r, g, b) == bg):
            continue
        h[int(0.2126 * r + 0.7152 * g + 0.0722 * b)] += 1
    return h


def main():
    n_idx, e_idx = index(NORDEN_UI), index(EDGE_UI)
    common = sorted(set(n_idx) & set(e_idx))
    if LIMIT:
        common = common[:LIMIT]
    if not common:
        sys.exit("no menus in common - check NORDEN_UI and EDGE_UI")
    jobs = [("norden", n, n_idx[n]) for n in common] + [("edge", n, e_idx[n]) for n in common]
    print(f"{len(common)} menus in both mods, rendering {len(jobs)} frames")
    with ThreadPoolExecutor(4) as ex:
        done = [r for r in ex.map(render, jobs) if r]
    print(f"rendered {len(done)}")

    per = {"norden": collections.Counter(), "edge": collections.Counter()}
    per_menu = collections.defaultdict(dict)
    for tag, name, png, swf in done:
        try:
            h = histogram(png, stage_bg(swf))
        except Exception as exc:
            print("  skip", name, exc)
            continue
        per[tag].update(h)
        if sum(h.values()) >= MIN_PX:
            per_menu[name][tag] = h
    both = {n: v for n, v in per_menu.items() if len(v) == 2}
    print(f"{len(both)} menus measurable on both sides (>= {MIN_PX} visible px each)")

    json.dump({
        "note": "Luminance histograms of rendered frame 1, visible pixels only (alpha>8), stage "
                "background removed. This census reflects screen area; edge-roles.json reflects how "
                "the art is built. Regenerate with tools/render-census.py.",
        "min_px": MIN_PX,
        "menus": {n: {t: {str(k): v for k, v in sorted(h.items())} for t, h in sides.items()}
                  for n, sides in sorted(both.items())},
        "norden": {str(k): v for k, v in sorted(per["norden"].items())},
        "edge": {str(k): v for k, v in sorted(per["edge"].items())},
    }, open(OUT, "w", encoding="utf-8"), separators=(",", ":"))

    def q(c, f):
        tot = sum(c.values())
        acc = 0
        for k in sorted(c):
            acc += c[k]
            if acc >= tot * f:
                return k
        return 255
    for tag in ("norden", "edge"):
        c = per[tag]
        tot = sum(c.values()) or 1
        print(f"  {tag:7} {tot/1e6:6.1f} Mpx  p10={q(c,.1):3d} p25={q(c,.25):3d} p50={q(c,.5):3d} "
              f"p75={q(c,.75):3d} p90={q(c,.9):3d}")
        bands = [(0, 32, "near-black"), (32, 100, "dark"), (100, 150, "mid"),
                 (150, 220, "light"), (220, 256, "near-white")]
        print("          " + "  ".join(
            f"{lbl} {100*sum(v for k, v in c.items() if lo <= k < hi)/tot:.0f}%" for lo, hi, lbl in bands))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
