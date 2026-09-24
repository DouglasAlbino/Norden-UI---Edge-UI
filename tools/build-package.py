r"""Assemble the installable archive from EDGE_OUT: stamp the version, drop in dist\README.txt, zip.

    python build-package.py            -> build\Norden UI - Edge Colours <VERSION>.zip
    python build-package.py --verify   run tools/verify.py first and refuse to package a failing build
"""
import os, sys, subprocess, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.environ.get("EDGE_OUT", r"D:\mods\unpublished Norden UI - Edge Colours")
VERSION = open(os.path.join(ROOT, "VERSION"), encoding="utf-8-sig").read().strip()
OUT = os.path.join(ROOT, "build", f"Norden UI - Edge Colours {VERSION}.zip")

if "--verify" in sys.argv:
    if subprocess.run([sys.executable, os.path.join(ROOT, "tools", "verify.py")]).returncode:
        sys.exit("verify.py failed - not packaging")

if not os.path.isdir(MOD):
    sys.exit(f"nothing at {MOD} - run recolour.py --build first")

readme = open(os.path.join(ROOT, "dist", "README.txt"), encoding="utf-8").read()
readme = readme.replace("{VERSION}", VERSION)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
n = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(MOD):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, MOD))
            n += 1
    z.writestr("README.txt", readme)
print(f"{OUT}: {n} files, {os.path.getsize(OUT) / 1e6:.1f} MB")
