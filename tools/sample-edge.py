r"""Measure Edge UI's own palette and write the anchors this recolour maps onto.

The shipped palette/edge-ui.json is a fallback. This reads Edge UI's exported XML (and, with
--svg, its SVGs), censuses every colour node, and derives from Edge's real art:

  * its neutral ramp - the greys it actually paints panels, headers, hover states and text with,
    ranked by how much surface they carry (node count x files they appear in);
  * its accent - the most used saturated colour.

Norden's own ramp (measured the same way from build\xml, or the known defaults) is then paired
with Edge's, rank by rank: Norden's darkest heavily-used grey -> Edge's darkest heavily-used grey,
and so on, with 0->0 and 255->255 pinned. That pairing is the neutral_ramp of the output palette.

    python sample-edge.py             report only
    python sample-edge.py --write     write palette/edge-ui.measured.json (preferred by recolour.py)
    python sample-edge.py --svg       also read .svg colours from EDGE_UI
"""
import os, re, sys, json, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE_XML = os.environ.get("EDGE_XML", os.path.join(ROOT, "build", "xml-edge"))
NORDEN_XML = os.environ.get("NORDEN_XML", os.path.join(ROOT, "build", "xml"))
EDGE_UI = os.environ.get("EDGE_UI", r"D:\mods\Edge UI")
OUT = os.path.join(ROOT, "palette", "edge-ui.measured.json")

NODE = re.compile(r'<(\w+) type="(RGBA?)"((?:\s+\w+="[^"]*")+)/>')
ATTR = re.compile(r'(\w+)="([^"]*)"')
HEX = re.compile(r'\b(?:fill|stroke|stop-color|flood-color|lighting-color)\s*[:=]\s*"?(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})')

# Norden UI's ramp as measured by NordenUIBlack's survey (used when build\xml is absent).
NORDEN_FALLBACK = [26, 34, 51, 64, 88, 102, 128, 160, 192, 208, 224]


def census(xml_dir, svg_dir=None):
    count = collections.Counter()
    files = collections.defaultdict(set)
    for root, _, fs in os.walk(xml_dir):
        for f in fs:
            if not f.lower().endswith(".xml"):
                continue
            p = os.path.join(root, f)
            s = open(p, encoding="utf-8", errors="replace").read()
            for m in NODE.finditer(s):
                a = dict(ATTR.findall(m.group(3)))
                k = (int(a.get("red", 0)), int(a.get("green", 0)), int(a.get("blue", 0)))
                count[k] += 1
                files[k].add(p)
    if svg_dir:
        for root, _, fs in os.walk(svg_dir):
            for f in fs:
                if not f.lower().endswith(".svg"):
                    continue
                p = os.path.join(root, f)
                for h in HEX.findall(open(p, encoding="utf-8", errors="replace").read()):
                    h = h[1:]
                    if len(h) == 3:
                        h = "".join(c * 2 for c in h)
                    k = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
                    count[k] += 1
                    files[k].add(p)
    return count, files


def neutrals(count, files, spread=3, top=11):
    weight = collections.Counter()
    for k, c in count.items():
        if max(k) - min(k) <= spread:
            weight[round(sum(k) / 3)] += c * (1 + len(files[k]))
    return sorted(v for v, _ in weight.most_common(top)), weight


def accent(count, files, min_sat=25):
    best, score = None, -1
    for k, c in count.items():
        if max(k) - min(k) < min_sat:
            continue
        s = c * (1 + len(files[k]))
        if s > score:
            best, score = k, s
    return best


def pair(norden, edge):
    """Rank-by-rank pairing of two ramps, pinned at 0 and 255, kept monotone."""
    n, e = sorted(norden), sorted(edge)
    if not n or not e:
        return [[0, 0], [255, 255]]
    out, last = [[0, 0]], 0
    for i, v in enumerate(n):
        if v in (0, 255):
            continue
        j = round(i * (len(e) - 1) / max(1, len(n) - 1))
        y = max(last, min(255, e[j]))
        if out[-1][0] != v:
            out.append([v, y])
            last = y
    out.append([255, 255])
    return out


def main():
    if not os.path.isdir(EDGE_XML):
        sys.exit(f"no Edge XML at {EDGE_XML} - run: python export-xml.py --edge")
    ec, ef = census(EDGE_XML, EDGE_UI if "--svg" in sys.argv else None)
    e_ramp, e_w = neutrals(ec, ef)
    e_acc = accent(ec, ef)
    if os.path.isdir(NORDEN_XML):
        nc, nf = census(NORDEN_XML)
        n_ramp, _ = neutrals(nc, nf)
        src = "measured from " + NORDEN_XML
    else:
        n_ramp, src = NORDEN_FALLBACK, "NordenUIBlack survey defaults"

    print(f"Edge:   {len(ec)} distinct colours, neutral ramp {e_ramp}, accent {e_acc}")
    print(f"Norden: ramp {n_ramp}  ({src})")
    ramp = pair(n_ramp, e_ramp)
    print("mapping:", ramp)

    if "--write" in sys.argv:
        base = json.load(open(os.path.join(ROOT, "palette", "edge-ui.json"), encoding="utf-8-sig"))
        base.update({
            "name": "Edge UI (measured)",
            "note": f"Written by tools/sample-edge.py from {EDGE_XML}; Norden ramp {src}.",
            "neutral_ramp": ramp,
            "accent": list(e_acc) if e_acc else base["accent"],
            "panel": [ramp[1][1]] * 3 if len(ramp) > 1 else base["panel"],
        })
        json.dump(base, open(OUT, "w", encoding="utf-8", newline="\n"), indent=2)
        print("wrote", OUT)


if __name__ == "__main__":
    main()
