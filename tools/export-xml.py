r"""Every SWF of a mod -> JPEXS XML (ffdec-cli -swf2xml), 6 at a time, mirroring the Interface tree.

    set NORDEN_UI=D:\mods\Norden UI
    python export-xml.py                 -> build\xml        (Norden, the art we recolour)
    set EDGE_UI=D:\mods\Edge UI
    python export-xml.py --edge          -> build\xml-edge   (Edge, read only, for sample-edge.py)

FFDEC can be pointed elsewhere with the FFDEC environment variable.
"""
import os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

FF = os.environ.get("FFDEC", r"C:\Program Files (x86)\FFDec\ffdec-cli.exe")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = "--edge" in sys.argv
if EDGE:
    SRC = os.environ.get("EDGE_UI", r"D:\mods\Edge UI")
    OUT = os.environ.get("EDGE_XML", os.path.join(ROOT, "build", "xml-edge"))
else:
    SRC = os.environ.get("NORDEN_UI", r"D:\mods\Norden UI")
    OUT = os.environ.get("NORDEN_XML", os.path.join(ROOT, "build", "xml"))

jobs = []
for root, _, files in os.walk(SRC):
    for f in files:
        if f.lower().endswith(".swf"):
            src = os.path.join(root, f)
            rel = os.path.relpath(src, SRC)
            jobs.append((src, os.path.join(OUT, rel[:-4] + ".xml")))


def run(j):
    src, dst = j
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return "cached"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    r = subprocess.run([FF, "-swf2xml", src, dst], capture_output=True, text=True)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return "ok"
    return "FAIL " + src + " " + (r.stderr or r.stdout)[-300:]


if not jobs:
    sys.exit(f"no SWFs under {SRC} - set {'EDGE_UI' if EDGE else 'NORDEN_UI'}")
t = time.time()
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(run, jobs))
bad = [r for r in res if r.startswith("FAIL")]
print(f"{SRC} -> {OUT}: {len(jobs)} swfs, {len(bad)} failed, {time.time() - t:.0f}s")
for b in bad:
    print(b)
sys.exit(1 if bad else 0)
