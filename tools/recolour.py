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
stats = collections.Counter()


def fix(m):
    a = dict(ATTR.findall(m.group(3)))
    rgb = (int(a["red"]), int(a["green"]), int(a["blue"]))
    new = P.map_rgb(rgb, pal, accents=accents)
    if new == rgb:
        return m.group(0)
    stats[(rgb, new)] += 1
    it = iter(new)
    return re.sub(r'(red|green|blue)="\d+"', lambda mm: f'{mm.group(1)}="{next(it)}"', m.group(0))


def main():
    if not os.path.isdir(SRC_XML):
        sys.exit(f"no Norden XML at {SRC_XML} - run: python export-xml.py")
    print(f"palette: {pal['name']} ({os.path.relpath(pal['_path'], ROOT)}), accents={'on' if accents else 'off'}")
    jobs = []
    for root, _, files in os.walk(SRC_XML):
        for f in files:
            if not f.endswith(".xml"):
                continue
            src = os.path.join(root, f)
            rel = os.path.relpath(src, SRC_XML)
            dst = os.path.join(DST_XML, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
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
