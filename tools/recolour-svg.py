r"""The same Norden->Edge rule on Norden UI's SVG art (its Wheeler icon sets).

Colour attributes fill / stroke / stop-color / flood-color / lighting-color, including inside
style="...", go through palette.map_rgb. Opacity attributes are never touched.

    python recolour-svg.py            report what would change
    python recolour-svg.py --write    write the changed files under EDGE_OUT and read them back
    NORDEN_SVG_ALL=1                  walk the whole NORDEN_UI tree, not just SKSE\Plugins\wheeler
"""
import os, re, sys, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import palette as P

_ALL = os.environ.get("NORDEN_SVG_ALL") == "1"
_SUB = () if _ALL else ("SKSE", "Plugins", "wheeler")
SRC = os.path.join(os.environ.get("NORDEN_UI", r"D:\mods\Norden UI"), *_SUB)
DST = os.path.join(os.environ.get("EDGE_OUT", r"D:\mods\unpublished Norden UI - Edge Colours"), *_SUB)

HEX = re.compile(r'(?P<key>\b(?:fill|stroke|stop-color|flood-color|lighting-color)\s*[:=]\s*"?)'
                 r'(?P<hex>#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})(?![0-9a-fA-F])')

pal = P.load()
accents = "--accents" in sys.argv
stats = collections.Counter()


def parse(h):
    h = h[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def fix(m):
    rgb = parse(m.group("hex"))
    new = P.map_rgb(rgb, pal, accents=accents)
    if new == rgb:
        return m.group(0)
    out = "#%02x%02x%02x" % new
    stats[(m.group("hex").lower(), out)] += 1
    return m.group("key") + out


def main():
    if not os.path.isdir(SRC):
        sys.exit(f"no SVGs at {SRC} - set NORDEN_UI (and NORDEN_SVG_ALL=1 for the whole tree)")
    changed = []
    for root, _, files in os.walk(SRC):
        for f in files:
            if not f.lower().endswith(".svg"):
                continue
            p = os.path.join(root, f)
            s = open(p, encoding="utf-8", errors="replace").read()
            s2 = HEX.sub(fix, s)
            if s2 != s:
                changed.append((os.path.relpath(p, SRC), s2))
    print(f"{len(changed)} SVGs to recolour")
    for (a, b), c in sorted(stats.items(), key=lambda x: -x[1])[:20]:
        print(f"  {a} -> {b}  x{c}")

    if "--write" not in sys.argv:
        return 0
    bad = 0
    for rel, s2 in changed:
        out = os.path.join(DST, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8", newline="\n").write(s2)
        back = open(out, encoding="utf-8").read()
        # read-back: the file on disk must be exactly what we mapped, and every colour in it must be
        # a value the palette produces (an Edge value), never a Norden neutral that slipped through.
        targets = {P.map_rgb((v, v, v), pal)[0] for v in range(256)}
        left = [h.group("hex") for h in HEX.finditer(back)
                if P.is_neutral(parse(h.group("hex")), pal) and parse(h.group("hex"))[0] not in targets]
        if back != s2 or left:
            print("READ-BACK FAIL", out, left[:5])
            bad += 1
    print(f"wrote {len(changed) - bad} SVGs into {DST}, {bad} failed read-back")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
