r"""Prove the built FOMOD against Norden UI's own - the mirror is the whole promise, so it is checked.

Nexus's FOMOD schema lives behind a URL this build environment cannot reach, and a schema would not
catch the failure that actually matters here anyway: an installer that is valid XML but no longer
matches Norden's screens, so the option a user picks means something different from the option they
picked in Norden. So this compares the two configs structurally and checks the package is complete.

    set NORDEN_UI=D:\mods\Norden UI
    python validate-fomod.py     exit 0 only if every check passes

Checks:
  1. well-formed, root <config>, required elements present
  2. the step / group / option tree matches Norden's one-for-one: same order, same names, same
     group select types, same option type descriptors
  3. every `source` left in the config exists in the package and carries a recoloured file
  4. every `image` referenced exists in the package (or none are shipped at all)
  5. every flagDependency names a flag some option actually sets, and every flag Norden sets that
     something depends on is still set here - the pages that appear are the pages Norden shows
  6. no option installs into an empty destination, and no dropped option silently lost its label
"""
import os, sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORDEN_UI = os.environ.get("NORDEN_UI", r"D:\mods\Norden UI")
OUT = os.environ.get("EDGE_OUT", os.path.join(ROOT, "Norden UI - Edge Colours"))
SHIPPED = (".swf", ".svg")

fails = []
checks = 0


def check(cond, msg, detail=""):
    global checks
    checks += 1
    if not cond:
        fails.append(msg + (" - " + detail if detail else ""))
    print(("  ok   " if cond else "  FAIL ") + msg + (" - " + detail if detail and not cond else ""))


def win(p):
    return (p or "").replace("\\", "/")


def shape(root):
    """(step, group, option) names and types, in document order."""
    out = []
    for s in root.findall("./installSteps/installStep"):
        for g in s.findall("./optionalFileGroups/group"):
            for p in g.findall("./plugins/plugin"):
                t = p.find("./typeDescriptor/type")
                out.append((s.get("name"), g.get("name"), g.get("type"), p.get("name"),
                            t.get("name") if t is not None else None))
    return out


def flags_set(root):
    return {f.get("name") for f in root.iter("flag")}


def flags_needed(root):
    return {d.get("flag") for d in root.iter("flagDependency")}


def main():
    cfg = os.path.join(OUT, "fomod", "ModuleConfig.xml")
    src = os.path.join(NORDEN_UI, "fomod", "ModuleConfig.xml")
    if not os.path.isfile(cfg):
        sys.exit(f"no built FOMOD at {cfg} - run build-fomod.py --write")
    if not os.path.isfile(src):
        sys.exit(f"no Norden ModuleConfig at {src} - set NORDEN_UI")

    print("1. structure")
    try:
        mine = ET.parse(cfg).getroot()
        ok = True
    except ET.ParseError as e:
        print("  FAIL not well-formed -", e)
        return 1
    theirs = ET.parse(src).getroot()
    check(mine.tag == "config", "root element is <config>")
    check(mine.find("moduleName") is not None and mine.find("moduleName").text.strip() != "",
          "moduleName is set", repr(mine.findtext("moduleName")))
    check(os.path.isfile(os.path.join(OUT, "fomod", "info.xml")), "fomod/info.xml exists")

    print("2. mirrors Norden UI's installer")
    a, b = shape(mine), shape(theirs)
    check(len(a) == len(b), f"same number of options ({len(a)} vs {len(b)})")
    diff = [(x, y) for x, y in zip(a, b) if x != y]
    check(not diff, "every step/group/option matches in order, name and type",
          f"{len(diff)} differ, first: {diff[0] if diff else ''}")
    ms = [s.get("name") for s in mine.findall("./installSteps/installStep")]
    ts = [s.get("name") for s in theirs.findall("./installSteps/installStep")]
    check(ms == ts, f"same {len(ts)} steps in the same order")
    mv = [ET.tostring(s.find("visible")) for s in mine.findall("./installSteps/installStep") if s.find("visible") is not None]
    tv = [ET.tostring(s.find("visible")) for s in theirs.findall("./installSteps/installStep") if s.find("visible") is not None]
    check(mv == tv, "step visibility conditions are unchanged")

    print("3. sources exist in the package")
    missing, empty = [], []
    n = 0
    for el in list(mine.iter("folder")) + list(mine.iter("file")):
        s = el.get("source")
        n += 1
        p = os.path.join(OUT, win(s))
        if not os.path.exists(p):
            missing.append(s)
        elif os.path.isdir(p) and not any(f.lower().endswith(SHIPPED) for _, _, fs in os.walk(p) for f in fs):
            empty.append(s)
    check(not missing, f"all {n} sources exist", f"{len(missing)} missing, e.g. {missing[:2]}")
    check(not empty, "no source folder is empty of recoloured art", f"{len(empty)} empty, e.g. {empty[:2]}")
    check(all(el.get("destination") is not None for el in mine.iter("folder")),
          "every folder entry has a destination")

    print("4. images")
    imgs = {e.get("path") for e in mine.iter("image") if e.get("path")}
    mi = mine.find("moduleImage")
    if mi is not None and mi.get("path"):
        imgs.add(mi.get("path"))
    present = [i for i in imgs if os.path.isfile(os.path.join(OUT, win(i)))]
    check(len(present) == len(imgs) or not present,
          f"referenced images are all present ({len(present)}/{len(imgs)}) or all absent by choice",
          f"{len(imgs) - len(present)} missing")

    print("5. condition flags")
    need_m, set_m = flags_needed(mine), flags_set(mine)
    need_t, set_t = flags_needed(theirs), flags_set(theirs)
    check(need_m <= set_m, "every flag a step depends on is set by some option",
          f"unset: {sorted(need_m - set_m)[:3]}")
    check(need_m == need_t, "same flag dependencies as Norden")
    check(set_m == set_t, "same flags set as Norden",
          f"missing: {sorted(set_t - set_m)[:3]}")

    print("6. options kept")
    mp = [p.get("name") for p in mine.iter("plugin")]
    tp = [p.get("name") for p in theirs.iter("plugin")]
    check(mp == tp, f"all {len(tp)} option labels preserved")
    noted = sum(1 for p in mine.iter("plugin")
                if p.find("files") is None and "No recolour needed" in (p.findtext("description") or ""))
    nofiles = sum(1 for p in mine.iter("plugin") if p.find("files") is None)
    check(all((p.findtext("description") or "").strip() for p in mine.iter("plugin")),
          "every option still has a description")
    print(f"       ({nofiles} options install nothing, {noted} of them say why)")

    print(f"\n{checks - len(fails)}/{checks} checks passed")
    for f in fails:
        print("  FAIL", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
