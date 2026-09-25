r"""Norden UI's SWFs -> Edge UI's colours.

Every colour node in the exported JPEXS XML (fills, gradients, lines, text, backgrounds) goes
through palette.map_rgb: neutrals are remapped along the Norden->Edge ramp, hued colours are left
alone (unless --accents), alpha is never touched. Then -xml2swf back into the mod folder.

    set NORDEN_XML=...\build\xml          (from export-xml.py)
    python recolour.py                    report what would change
    python recolour.py --build            write build\xml-edge-out and rebuild the SWFs into EDGE_OUT
    python recolour.py --build --accents  also pull hued colours onto Edge's accent

Output SWFs land at the SAME relative path under EDGE_OUT, so the result is a mod that loads after
Norden UI and wins. Only files whose colours actually changed are rebuilt.
"""
import os, re, sys, time, collections, subprocess
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import palette as P

FF = os.environ.get("FFDEC", r"C:\Program Files (x86)\FFDec\ffdec-cli.exe")
ROOT = P.ROOT
SRC_XML = os.environ.get("NORDEN_XML", os.path.join(ROOT, "build", "xml"))
DST_XML = os.environ.get("NORDEN_XML_EDGE", os.path.join(ROOT, "build", "xml-edge-out"))
MOD = os.environ.get("EDGE_OUT", r"D:\mods\unpublished Norden UI - Edge Colours")

NODE = re.compile(r'<(\w+) type="(RGBA?)"((?:\s+\w+="[^"]*")+)/>')
ATTR = re.compile(r'(\w+)="([^"]*)"')

pal = P.load()
accents = "--accents" in sys.argv
# The colour-temperature transfer (1.1.0) needs to know which menu and which kind of node it is
# looking at, so the mapping is per file and per role rather than one global table. --flat falls back
# to 1.0.0 behaviour: the neutral ramp only, no warmth.
transfer = "--flat" not in sys.argv and os.path.exists(P.ROLES_PATH)
stats = collections.Counter()
_current = {"name": ""}


def fix(m):
    a = dict(ATTR.findall(m.group(3)))
    rgb = (int(a["red"]), int(a["green"]), int(a["blue"]))
    if transfer:
        new = P.transfer(rgb, pal, m.group(1), _current["name"])
    else:
        new = P.map_rgb(rgb, pal, accents=accents)
    if new == rgb:
        return m.group(0)
    stats[(rgb, new)] += 1
    # Substitute BY ATTRIBUTE NAME. JPEXS writes the attributes alphabetically - alpha, blue, green,
    # red - so feeding the new values positionally in R,G,B order silently swaps red and blue. On
    # neutral greys (r=g=b) that is invisible, which is how it survived 1.0.0: the only non-neutral
    # output then was the gold #ffd700 -> #f5d87c, shipped as #7cd8f5, a pale blue. That is why the
    # first install showed none of Edge's gold.
    channel = {"red": new[0], "green": new[1], "blue": new[2]}
    return re.sub(r'(red|green|blue)="\d+"', lambda mm: f'{mm.group(1)}="{channel[mm.group(1)]}"', m.group(0))


def selftest():
    """The regression that shipped in 1.0.0: attribute order must not decide which channel gets what."""
    global stats
    ok = True
    for node in ('<textColor type="RGBA" alpha="255" blue="235" green="235" red="235"/>',
                 '<color type="RGB" red="235" green="235" blue="235"/>'):
        stats = collections.Counter()
        role = "textColor" if "textColor" in node else "color"
        out = NODE.sub(fix, node)
        got = {k: int(v) for k, v in ATTR.findall(out) if k in ("red", "green", "blue")}
        exp = (P.transfer((235, 235, 235), pal, role, _current["name"]) if transfer
               else P.map_rgb((235, 235, 235), pal))
        good = (got["red"], got["green"], got["blue"]) == tuple(exp)
        print(("  ok   " if good else "  FAIL ") + f"{role:9} {node[:22]}... -> {got} (expected {exp})")
        ok = ok and good
    return ok


def main():
    if "--selftest" in sys.argv:
        _current["name"] = "quest_journal.xml"
        sys.exit(0 if selftest() else 1)
    if not os.path.isdir(SRC_XML):
        sys.exit(f"no Norden XML at {SRC_XML} - run: python export-xml.py")
    print(f"palette: {pal['name']} ({os.path.relpath(pal['_path'], ROOT)}), "
          f"mode={'colour-temperature transfer' if transfer else 'flat ramp'}")
    jobs = []
    for root, _, files in os.walk(SRC_XML):
        for f in files:
            if not f.endswith(".xml"):
                continue
            src = os.path.join(root, f)
            rel = os.path.relpath(src, SRC_XML)
            dst = os.path.join(DST_XML, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            _current["name"] = f
            s = open(src, encoding="utf-8").read()
            s2 = NODE.sub(fix, s)
            open(dst, "w", encoding="utf-8", newline="\n").write(s2)
            jobs.append((dst, os.path.join(MOD, rel[:-4] + ".swf"), s != s2))

    changed = [j for j in jobs if j[2]]
    print(f"{len(jobs)} files, {len(changed)} with a colour to remap")
    for (a, b), c in sorted(stats.items(), key=lambda x: -x[1])[:24]:
        print(f"  #{a[0]:02x}{a[1]:02x}{a[2]:02x} -> #{b[0]:02x}{b[1]:02x}{b[2]:02x}  x{c}")

    if "--build" not in sys.argv:
        return 0

    def build(j):
        dst, out, _ = j
        os.makedirs(os.path.dirname(out), exist_ok=True)
        r = subprocess.run([FF, "-xml2swf", dst, out], capture_output=True, text=True)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return out
        return "FAIL " + dst + (r.stderr or r.stdout)[-200:]

    t = time.time()
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(build, changed))
    bad = [r for r in res if r.startswith("FAIL")]
    print(f"built {len(res) - len(bad)} swfs, {len(bad)} failed, {time.time() - t:.0f}s")
    for b in bad:
        print(b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
