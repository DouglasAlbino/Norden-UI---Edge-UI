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
# A proposal, deliberately NOT edge-ui.measured.json: the shipped mapping is curated from this
# census (see docs/census.md) because a nearest-snap over Edge's full ramp lightens some of Norden's
# mid greys - Edge's ramp has sparse noise values (14, 26, 191, 203, 211) next to the tones it
# really paints. Review a proposal before promoting it.
OUT = os.path.join(ROOT, "palette", "edge-ui.proposed.json")

NODE = re.compile(r'<(\w+) type="(RGBA?)"((?:\s+\w+="[^"]*")+)/>')
ATTR = re.compile(r'(\w+)="([^"]*)"')
HEX = re.compile(r'\b(?:fill|stroke|stop-color|flood-color|lighting-color)\s*[:=]\s*"?(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})')

# Norden UI's ramp as measured by NordenUIBlack's survey (used when build\xml is absent).
NORDEN_FALLBACK = [26, 34, 51, 64, 88, 102, 128, 160, 192, 208, 224]


def census(xml_dir, svg_dir=None):
    """Colour -> node count, the files it appears in, and the XML node names it appears under.

    The node name matters: `backgroundColor` is the SWF stage colour, which Scaleform does not paint
    in game. Edge UI carries #333333 as a stage background in 291 of its 321 files while painting
    almost nothing with it, so a census that ignores roles reads Edge as a grey-panelled UI when it
    is in fact black-panelled."""
    count = collections.Counter()
    files = collections.defaultdict(set)
    roles = collections.defaultdict(collections.Counter)
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
                roles[k][m.group(1)] += 1
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
                    roles[k]["svg"] += 1
    return count, files, roles


def neutrals(count, files, roles, spread=3, top=11, painted_only=True):
    """Neutral values ranked by surface weight, counting only painted nodes when painted_only."""
    weight = collections.Counter()
    for k, c in count.items():
        if max(k) - min(k) > spread:
            continue
        n = c - (roles[k]["backgroundColor"] if painted_only else 0)
        if n <= 0:
            continue
        weight[round(sum(k) / 3)] += n * (1 + len(files[k]))
    return sorted(v for v, _ in weight.most_common(top)), weight


# Scaleform mask / colour-transform placeholders: saturated, widespread, and never a real accent.
MASKS = {(0, 255, 0), (0, 255, 255), (255, 0, 255)}


def accents(count, files, roles, min_sat=25, top=6):
    """The mod's real accent colours: saturated, not masks, and preferably used as text.

    Ranking by raw count alone returns #00ff00 - a mask Scaleform replaces at run time - as Edge's
    "accent". Masks are excluded outright and textColor nodes are weighted up, which is what makes
    Edge's cream/gold family (#ece2b7, #f5d87c, #aaa07a) come out on top."""
    scored = []
    for k, c in count.items():
        if max(k) - min(k) < min_sat or k in MASKS:
            continue
        text = roles[k]["textColor"]
        scored.append((c * (1 + len(files[k])) * (3 if text else 1), k, text))
    scored.sort(reverse=True)
    return [k for _, k, _ in scored[:top]], [k for _, k, t in scored[:top] if t]


def snap(v, ramp):
    """Nearest value in the target ramp - monotone, so grey order survives."""
    return min(ramp, key=lambda y: (abs(y - v), y))


def pair(norden, edge, pull=0.6):
    """Norden's ramp -> Edge's, as anchors for a piecewise-linear curve.

    Each Norden value is snapped to the nearest value Edge actually paints, then moved only `pull`
    of the way there. Two reasons not to snap outright: Norden and Edge already share most of their
    ramp (0, 153, 204, 255), so a hard snap mostly moves values that did not need moving; and
    collapsing every neutral onto a six-value ramp would band Norden's gradients. The partial pull
    keeps gradients smooth while shifting the distribution onto Edge's.

    Anchors are forced strictly monotone, so panel < header < hover < divider never collapses.
    """
    n, e = sorted(set(norden) | {0, 255}), sorted(set(edge) | {0, 255})
    out, last = [], -1
    for v in n:
        y = v if v in (0, 255) else round(v + (snap(v, e) - v) * pull)
        y = max(last + 1, min(255, y)) if 0 < v < 255 else v
        if out and out[-1][0] == v:
            continue
        out.append([v, y])
        last = y
    return out


def main():
    if not os.path.isdir(EDGE_XML):
        sys.exit(f"no Edge XML at {EDGE_XML} - run: python export-xml.py --edge")
    ec, ef, er = census(EDGE_XML, EDGE_UI if "--svg" in sys.argv else None)
    top = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--top=")), 6))
    e_ramp, e_w = neutrals(ec, ef, er, top=top)
    e_all, e_text = accents(ec, ef, er)
    e_acc = (e_text or e_all or [None])[0]
    if os.path.isdir(NORDEN_XML):
        nc, nf, nr = census(NORDEN_XML)
        n_ramp, _ = neutrals(nc, nf, nr)
        src = "measured from " + NORDEN_XML
    else:
        n_ramp, src = NORDEN_FALLBACK, "NordenUIBlack survey defaults"

    print(f"Edge:   {len(ec)} distinct colours, painted neutral ramp {e_ramp}")
    print(f"        accents {['#%02x%02x%02x' % k for k in e_all]}, chosen {e_acc}")
    print(f"Norden: ramp {n_ramp}  ({src})")
    ramp = pair(n_ramp, e_ramp)
    print("proposed mapping:", ramp)
    cur = os.path.join(ROOT, "palette", "edge-ui.measured.json")
    if os.path.exists(cur):
        print("shipped mapping:  ", json.load(open(cur, encoding="utf-8-sig"))["neutral_ramp"])

    if "--write" in sys.argv:
        base = json.load(open(os.path.join(ROOT, "palette", "edge-ui.json"), encoding="utf-8-sig"))
        base.update({
            "name": "Edge UI (measured)",
            "note": f"Written by tools/sample-edge.py from {EDGE_XML}; Norden ramp {src}.",
            "neutral_ramp": ramp,
            "accent": list(e_acc) if e_acc else base["accent"],
            "protected": ["%02x%02x%02x" % k for k in MASKS],
            "panel": [ramp[1][1]] * 3 if len(ramp) > 1 else base["panel"],
        })
        json.dump(base, open(OUT, "w", encoding="utf-8", newline="\n"), indent=2)
        print("wrote", OUT, "- review it, then copy onto palette/edge-ui.measured.json to ship it")


if __name__ == "__main__":
    main()
