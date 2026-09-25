r"""Norden UI's own installer, mirrored, pointing at the recoloured files.

This does not invent an installer. It reads Norden UI's `fomod/ModuleConfig.xml` and rewrites it in
place-for-place: the same 18 steps in the same order, the same groups with the same select types,
the same 251 options with the same names, images, condition flags and flag dependencies. Anyone who
has installed Norden UI sees exactly the screens they saw there, so the option they pick here is the
option they picked there.

Two things change.

1. **Sources are pruned to what was actually recoloured.** This mod is an overlay: it only needs to
   ship the files whose colours moved. An option whose folder contains no recoloured file installs
   nothing, so its `<folder>`/`<file>` entries are dropped. The option itself is KEPT - removing it
   would renumber the screens and break the mirror - and its description gains one line saying
   Norden's own file already matches, so the user is not left wondering.
2. **Names point at this mod**, not at Norden UI.

Condition flags are copied verbatim, which matters: Norden's later steps (the 21x9 pages, the TMO
and Major Patches pages) are shown or hidden by flags set on earlier screens, and a flag dropped
here would silently strip pages out of the installer.

    set NORDEN_UI=D:\mods\Norden UI
    set EDGE_OUT=...\Norden UI - Edge Colours
    python build-fomod.py                report what it would build
    python build-fomod.py --write        write fomod\ (and Images\) into EDGE_OUT
    python build-fomod.py --write --no-images    skip Norden's installer screenshots
"""
import os, sys, shutil, collections
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORDEN_UI = os.environ.get("NORDEN_UI", r"D:\mods\Norden UI")
OUT = os.environ.get("EDGE_OUT", os.path.join(ROOT, "Norden UI - Edge Colours"))
VERSION = open(os.path.join(ROOT, "VERSION"), encoding="utf-8-sig").read().strip()
SRC_CFG = os.path.join(NORDEN_UI, "fomod", "ModuleConfig.xml")

MOD_NAME = "Norden UI - Edge Colours"
EMPTY_NOTE = "  [No recolour needed: Norden UI's own file for this option already matches Edge's palette.]"
SHIPPED = (".swf", ".svg")


def win(p):
    return (p or "").replace("\\", "/")


def has_recoloured(rel):
    """Does our output carry anything for this installer source?"""
    p = os.path.join(OUT, win(rel))
    if os.path.isfile(p):
        return True
    if not os.path.isdir(p):
        return False
    return any(f.lower().endswith(SHIPPED) for _, _, fs in os.walk(p) for f in fs)


def main():
    if not os.path.isfile(SRC_CFG):
        sys.exit(f"no ModuleConfig.xml at {SRC_CFG} - set NORDEN_UI")
    if not os.path.isdir(OUT):
        sys.exit(f"no recoloured output at {OUT} - run recolour.py --build first")

    tree = ET.parse(SRC_CFG)
    root = tree.getroot()
    stat = collections.Counter()

    # 1. name it after this mod
    root.find("moduleName").text = MOD_NAME

    # 2. prune sources that carry nothing of ours; keep every option
    images = set()
    mi = root.find("moduleImage")
    if mi is not None and mi.get("path"):
        images.add(mi.get("path"))

    for plugin in root.iter("plugin"):
        stat["options"] += 1
        img = plugin.find("image")
        if img is not None and img.get("path"):
            images.add(img.get("path"))
        files = plugin.find("files")
        if files is None:
            stat["options_without_files"] += 1
            continue
        kept = 0
        for el in list(files):
            src = el.get("source")
            if has_recoloured(src):
                kept += 1
                stat["sources_kept"] += 1
            else:
                files.remove(el)
                stat["sources_dropped"] += 1
        if kept == 0:
            plugin.remove(files)
            stat["options_emptied"] += 1
            d = plugin.find("description")
            if d is not None and EMPTY_NOTE not in (d.text or ""):
                d.text = ((d.text or "").rstrip() + "\n\n" + EMPTY_NOTE).strip()
        else:
            stat["options_installing"] += 1

    steps = root.findall("./installSteps/installStep")
    groups = root.findall(".//group")
    flags = root.findall(".//conditionFlags/flag")
    deps = root.findall(".//flagDependency")
    print(f"mirrored: {len(steps)} steps, {len(groups)} groups, {stat['options']} options, "
          f"{len(flags)} condition flags, {len(deps)} flag dependencies")
    print(f"sources: {stat['sources_kept']} kept, {stat['sources_dropped']} dropped (nothing recoloured there)")
    print(f"options: {stat['options_installing']} install files, {stat['options_emptied']} annotated as already matching")
    print(f"images referenced: {len(images)}")

    if "--write" not in sys.argv:
        print("\n(dry run - pass --write to write the FOMOD)")
        return 0

    fomod = os.path.join(OUT, "fomod")
    os.makedirs(fomod, exist_ok=True)
    tree.write(os.path.join(fomod, "ModuleConfig.xml"), encoding="utf-8", xml_declaration=True)

    info = ET.Element("fomod")
    for tag, text in (("Name", MOD_NAME), ("Author", "recolour of Norden UI by Nithog"),
                      ("Version", VERSION),
                      ("Website", "https://www.nexusmods.com/skyrimspecialedition/mods/166086"),
                      ("Description",
                       "Norden UI wearing Edge UI's colours. Norden's layout, icons and animations are "
                       "unchanged; its neutral ramp is remapped onto Edge UI's measured palette and its "
                       "gold text onto Edge's cream/gold. Requires Norden UI - install this after it. "
                       "This installer mirrors Norden UI's own: pick the same options you picked there.")):
        ET.SubElement(info, tag).text = text
    ET.ElementTree(info).write(os.path.join(fomod, "info.xml"), encoding="utf-8", xml_declaration=True)

    copied = 0
    if "--no-images" not in sys.argv:
        for rel in sorted(images):
            src = os.path.join(NORDEN_UI, win(rel))
            dst = os.path.join(OUT, win(rel))
            if os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
        print(f"copied {copied}/{len(images)} installer images")
    else:
        print("images skipped (--no-images): the installer will show option names without screenshots")

    print(f"wrote {fomod}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
