r"""Run the FOMOD the way a mod manager would, and see what lands on disk.

Validation proves the installer matches Norden's. This proves it *works*: it walks the steps in
order, evaluates each step's visibility against the flags set so far (exactly as Vortex / MO2 do),
picks options, applies every `<folder>`/`<file>` entry to a destination tree, and reports it.

Choosing is deliberate rather than random:
  SelectExactlyOne / SelectAtMostOne -> the first option whose name is not a "none" variant, so the
  simulation exercises real content instead of the opt-out;
  SelectAll / SelectAny             -> everything (SelectAny is the widest case, which is what a
                                       validation run wants);
  --choose "Group=Option"           -> override a specific group, repeatable.

    python install-with-choices.py                       simulate, report only
    python install-with-choices.py --out D:\tmp\install  actually copy the files there
    python install-with-choices.py --resolution 21x9     drive the resolution branch
"""
import os, re, sys, shutil, collections
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("EDGE_OUT", os.path.join(ROOT, "Norden UI - Edge Colours"))
NONE = re.compile(r"^(none|no|don'?t|do not|without|vanilla|skip|keep)\b", re.I)
NUMBERED = re.compile(r"^\s*\d+\s*[.)-]\s*")   # Norden labels every option "1. ", "2. " ...


def is_none(name):
    """Norden numbers its options, so the opt-out is "1. Skip", not "Skip"."""
    return bool(NONE.match(NUMBERED.sub("", name or "")))


def win(p):
    return (p or "").replace("\\", "/")


def arg(name, default=None):
    for a in sys.argv:
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def dep_ok(node, flags):
    """<dependencies operator=And|Or> of <flagDependency flag= value=>."""
    if node is None:
        return True
    op = (node.get("operator") or "And").lower()
    results = []
    for d in node.findall("flagDependency"):
        results.append(flags.get(d.get("flag"), "") == (d.get("value") or ""))
    for sub in node.findall("dependencies"):
        results.append(dep_ok(sub, flags))
    if not results:
        return True
    return all(results) if op == "and" else any(results)


def main():
    cfg = os.path.join(OUT, "fomod", "ModuleConfig.xml")
    if not os.path.isfile(cfg):
        sys.exit(f"no FOMOD at {cfg} - run build-fomod.py --write")
    root = ET.parse(cfg).getroot()

    overrides = {}
    for a in sys.argv:
        if a.startswith("--choose="):
            g, _, o = a.split("=", 1)[1].partition("=")
            overrides[g.strip()] = o.strip()
    res = arg("--resolution", "16x9")

    flags, chosen, ops = {}, [], []
    skipped = []
    for step in root.findall("./installSteps/installStep"):
        if not dep_ok(step.find("visible"), flags):
            skipped.append(step.get("name"))
            continue
        for group in step.findall("./optionalFileGroups/group"):
            plugins = group.findall("./plugins/plugin")
            gtype = group.get("type")
            if gtype in ("SelectAll", "SelectAny"):
                picked = plugins
            else:
                want = overrides.get(group.get("name"))
                picked = []
                if want:
                    picked = [p for p in plugins if p.get("name") == want]
                if not picked and group.get("name") == "Resolutions":
                    picked = [p for p in plugins if res.replace("x", "") in re.sub(r"\D", "", p.get("name") or "")] \
                             or [p for p in plugins if res in (p.get("name") or "")]
                if not picked:
                    # Prefer an option that actually installs something. Norden numbers its options
                    # "1. ...", "2. ..." and the first one is usually the opt-out, so "first option
                    # that is not named like a none" still lands on an empty choice in most groups
                    # and the simulation proves nothing.
                    live = [p for p in plugins if not is_none(p.get("name"))]
                    real = [p for p in live if p.find("files") is not None]
                    # A group can install nothing and still matter: Norden's "Wheeler" step only sets
                    # the flag `wheeleryes`, and the Wheeler Style / Wheeler Icons steps - which do
                    # carry files - are hidden unless it is On. Prefer a flag-setter over a dead end.
                    unlocking = [p for p in live if p.findall("./conditionFlags/flag")]
                    picked = real[:1] or unlocking[:1] or live[:1] or plugins[:1]
            for p in picked:
                chosen.append((step.get("name"), group.get("name"), p.get("name")))
                for f in p.findall("./conditionFlags/flag"):
                    flags[f.get("name")] = (f.text or "")
                files = p.find("files")
                if files is None:
                    continue
                for el in files:
                    ops.append((el.tag, el.get("source"), el.get("destination") or ""))

    dest_root = arg("--out")
    installed = collections.Counter()
    for tag, s, d in ops:
        sp = os.path.join(OUT, win(s))
        if tag == "file":
            names = [(sp, win(d))]
        else:
            names = []
            for r, _, fs in os.walk(sp):
                for f in fs:
                    full = os.path.join(r, f)
                    names.append((full, os.path.join(win(d), os.path.relpath(full, sp)).replace("\\", "/")))
        for src, rel in names:
            installed[os.path.splitext(rel)[1].lower() or "(none)"] += 1
            if dest_root:
                t = os.path.join(dest_root, rel)
                os.makedirs(os.path.dirname(t), exist_ok=True)
                shutil.copy2(src, t)

    print(f"resolution: {res}")
    print(f"steps shown: {len(root.findall('./installSteps/installStep')) - len(skipped)}, "
          f"hidden by flags: {len(skipped)} {skipped}")
    print(f"flags set: {len(flags)}")
    print(f"options chosen: {len(chosen)}, install operations: {len(ops)}")
    print(f"files installed: {sum(installed.values())} {dict(installed.most_common(6))}")
    tops = collections.Counter(r.split("/")[0] for _, _, r in
                               [(0, 0, os.path.join(win(d), "x").replace("\\", "/")) for _, _, d in ops if d])
    print(f"destinations: {dict(tops)}")
    if dest_root:
        print(f"copied into {dest_root}")
    bad = [s for _, s, _ in ops if not os.path.exists(os.path.join(OUT, win(s)))]
    if bad:
        print(f"MISSING SOURCES: {len(bad)} e.g. {bad[:3]}")
        return 1
    if sum(installed.values()) == 0:
        print("NOTHING INSTALLED - the installer would produce an empty mod")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
