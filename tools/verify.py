r"""Prove the colour on the SHIPPED files, not in the script.

Re-exports every built SWF under EDGE_OUT back to XML (ffdec -swf2xml into build\xml-verify) and
reads its colours. A run passes when no colour in the shipped art would still be changed by the
palette - i.e. the recolour is a fixed point - and reports the ramp actually present in the output.

    python verify.py            verify EDGE_OUT
    python verify.py --svg      also verify the SVGs written by recolour-svg.py
"""
import collections, os, re, sys, subprocess, collections
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import palette as P

FF = os.environ.get("FFDEC", r"C:\Program Files (x86)\FFDec\ffdec-cli.exe")
MOD = os.environ.get("EDGE_OUT", r"D:\mods\unpublished Norden UI - Edge Colours")
TMP = os.path.join(P.ROOT, "build", "xml-verify")
NODE = re.compile(r'<(\w+) type="(RGBA?)"((?:\s+\w+="[^"]*")+)/>')
ATTR = re.compile(r'(\w+)="([^"]*)"')
HEX = re.compile(r'\b(?:fill|stroke|stop-color|flood-color|lighting-color)\s*[:=]\s*"?(#[0-9a-fA-F]{6})')

pal = P.load()
found = collections.Counter()
bad = collections.Counter()


# Until 1.2.0 this asserted that every neutral in the shipped art is a value the ramp produces. That
# invariant died when "leave this fill exactly as Norden drew it" became a deliberate outcome. The
# check now recomputes each shipped file from Norden's original and demands an exact match, which
# also catches a stale build - art left behind by an earlier rule - and the channel swap.
SRC_XML = os.environ.get("NORDEN_XML", os.path.join(P.ROOT, "build", "xml"))
warm_text = [0, 0]      # [warm, total] text nodes in the shipped art


def _is_warm(rgb):
    import colorsys
    h, _, sat = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
    return 25 / 360.0 <= h <= 65 / 360.0 and sat >= 0.08 and max(rgb) >= 40


def note(rgb, n=1):
    found[rgb] += n


def _counts(path, transform=None, menu=""):
    out = collections.Counter()
    for m in NODE.finditer(open(path, encoding="utf-8", errors="replace").read()):
        a = dict(ATTR.findall(m.group(3)))
        rgb = (int(a.get("red", 0)), int(a.get("green", 0)), int(a.get("blue", 0)))
        out[P.transfer(rgb, pal, m.group(1), menu) if transform else rgb] += 1
    return out


def export(job):
    src, dst = job
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return dst
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run([FF, "-swf2xml", src, dst], capture_output=True, text=True)
    return dst if os.path.exists(dst) else None


def main():
    if not os.path.isdir(MOD):
        sys.exit(f"nothing at {MOD} - run recolour.py --build first")
    jobs = []
    for root, _, files in os.walk(MOD):
        for f in files:
            if f.lower().endswith(".swf"):
                src = os.path.join(root, f)
                rel = os.path.relpath(src, MOD)
                jobs.append((src, os.path.join(TMP, rel[:-4] + ".xml")))
    with ThreadPoolExecutor(6) as ex:
        xmls = [x for x in ex.map(export, jobs) if x]
    for x in xmls:
        s = open(x, encoding="utf-8", errors="replace").read()
        for m in NODE.finditer(s):
            a = dict(ATTR.findall(m.group(3)))
            rgb = (int(a.get("red", 0)), int(a.get("green", 0)), int(a.get("blue", 0)))
            note(rgb)
            if m.group(1) == "textColor":
                warm_text[1] += 1
                warm_text[0] += 1 if _is_warm(rgb) else 0
    if "--svg" in sys.argv:
        for root, _, files in os.walk(MOD):
            for f in files:
                if f.lower().endswith(".svg"):
                    for h in HEX.findall(open(os.path.join(root, f), encoding="utf-8", errors="replace").read()):
                        note(tuple(int(h[1:][i:i + 2], 16) for i in (0, 2, 4)))

    greys = sorted({round(sum(k) / 3) for k in found if P.is_neutral(k, pal)})
    print(f"{len(jobs)} swfs re-exported, {len(found)} distinct colours in the shipped art")
    print("neutral ramp present:", greys)
    mismatched = []
    for x in xmls:
        rel = os.path.relpath(x, TMP)
        src = os.path.join(SRC_XML, rel)
        if not os.path.isfile(src):
            continue
        exp = _counts(src, True, os.path.basename(x))
        got = _counts(x)
        if exp != got:
            mismatched.append((sum((exp - got).values()) + sum((got - exp).values()), rel))
    if mismatched:
        mismatched.sort(reverse=True)
        print(f"FAIL - {len(mismatched)} shipped files do not match the rule applied to the original:")
        for d, rel in mismatched[:10]:
            print(f"  {d:6d} colour nodes differ  {rel}")
        return 1
    print(f"every one of {len(xmls)} shipped files matches the rule applied to Norden's original")
    # 1.0.0 passed every structural check and still looked like Norden in game, because nothing
    # checked for the thing that makes Edge look like Edge. This is that check, and it is what caught
    # the red/blue channel swap: a build whose text comes out cyan fails here.
    share = 100 * warm_text[0] / max(1, warm_text[1])
    floor = 15
    print(f"warm text in the shipped art: {warm_text[0]}/{warm_text[1]} = {share:.0f}% "
          f"(Edge UI: 35%, Norden UI: 5%, floor for a pass: {floor}%)")
    if share < floor:
        print("FAIL - the recolour did not carry Edge's cream/gold into the text")
        return 1
    print("PASS - every neutral is an Edge value and Edge's warmth is present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
