# Norden UI - Edge Colours

[Norden UI](https://www.nexusmods.com/skyrimspecialedition/mods/166086) (by Nithog) wearing
[Edge UI](https://www.nexusmods.com/skyrimspecialedition/mods/130983)'s (by Eugene) colours.
Norden's layout, spacing, icons and animations stay exactly as they are; only its neutral grey ramp
is remapped onto Edge's, so the panels go to Edge's near-black, headers, hover states and dividers
keep their relative order above the panel, and text lands on Edge's light grey. Hued colours
(Norden's slate blue-greys, the status red/green/gold) and every alpha value are untouched by
default. Requires Norden UI; loads above it.

Built as a sibling of [NordenUIBlack](https://github.com/ApocryphaRealm/NordenUIBlack/) and follows
the same rules: same tool layout, same "prove the colour on the shipped file" read-back, and **no
art in the repository**.

## No art here, by design

Norden UI's and Edge UI's permissions allow a modified release on Nexus with credit and forbid
uploading their files elsewhere. So every file that carries their art - the SWFs, the SVGs, the
intermediate XML, the measured palette taken from Edge's own art - is git-ignored and lives only on
the build machine. What this repository holds is the tooling and the colour rule.

## The colour rule

`tools/palette.py` is the single source of truth, and every other tool calls into it.

* A colour node counts as **neutral** when its channel spread (`max - min`) is `<= 3`. Those are the
  greys Norden builds panels out of - and only those are remapped.
* A neutral's value goes through `neutral_ramp`, a **piecewise-linear, monotone** curve from
  Norden's anchors to Edge's. Monotone matters: panel < header < hover < divider stays true, so the
  UI does not collapse into one flat block the way a single "subtract and halve" would at the dark
  end.
* **Hued colours are left alone.** Edge keeps Skyrim's status colours too. `--accents` optionally
  pulls saturated colours onto Edge's accent (`#aaa07a`) at their own brightness - off by default.
* **Alpha is never read and never written.** Every fade and opacity is Norden's own.

* **Masks are protected.** Both mods paint `#00ff00` and `#00ffff` into shapes Scaleform replaces at
  run time (730 nodes across 172 Norden files). Recolouring one breaks the effect, so they are
  listed in `protected` and never touched.

The shipped mapping in `palette/edge-ui.measured.json` is **measured**, not estimated: 321 Edge SWFs
(20 034 colour nodes) against 926 Norden SWFs (84 935 nodes). `docs/census.md` has the full census
and the reasoning. The short version:

* Both mods already agree on `0`, `153`, `204`, `255` and share six hued colours byte-for-byte, so
  those are left alone.
* Norden paints dark-mid surfaces at `25`/`48`/`88` where Edge paints `0`/`51`/`102`; the ramp pulls
  those down (`25 -> 13`, `48 -> 38`, `88 -> 72`, `102 -> 92`) and is identity through `128`-`204`.
* Norden's gold text `#ffd700`/`#ffd800` maps to Edge's `#f5d87c`/`#f6db85`.

`python tools/palette.py` prints the table; `--selftest` checks the invariants (14 checks).
`tools/sample-edge.py --write` re-derives a mapping from the art and writes it to
`palette/edge-ui.proposed.json` for review - never over the shipped one.

## Tools

| file | what it does |
| --- | --- |
| `tools/export-xml.py` | every Norden SWF to JPEXS XML (`ffdec-cli -swf2xml`) in `build/xml`; `--edge` does the same for Edge UI into `build/xml-edge` |
| `tools/sample-edge.py` | role-aware census of Edge's colours (stage background and masks excluded), derives ramp and accents, `--write`s a proposal |
| `tools/palette.py` | the rule itself: `map_rgb`, the ramp, the selftest |
| `tools/recolour.py --build` | remaps every colour node in Norden's XML and `-xml2swf`s the changed files into the output mod folder |
| `tools/recolour-svg.py --write` | the same rule on Norden's Wheeler SVGs, with read-back |
| `tools/verify.py` | re-exports the **shipped** SWFs and proves no Norden neutral survived |
| `tools/build-fomod.py` | rewrites Norden UI's own `ModuleConfig.xml` to point at the recoloured files - same steps, groups, options, images and flags |
| `tools/validate-fomod.py` | proves the built installer against Norden's, option for option (16 checks) |
| `tools/install-with-choices.py` | runs the FOMOD like a mod manager would - flags, hidden steps and all - and reports what lands on disk |
| `tools/build-package.py` | stamps `VERSION`, adds `package/README.txt`, zips the installable archive |

## Result of the current build

`Norden UI - Edge Colours/` is a finished, installable FOMOD:

* **896 of 926 SWFs** and **84 of 150 SVGs** recoloured, 0 build failures. `tools/verify.py --svg`
  re-exported all 896 shipped SWFs and passed.
* **The installer mirrors Norden UI's**: all 18 steps in order, 92 groups, **251 options** with the
  same names, images (110 of them) and select types, and all 94 condition flags and 24 flag
  dependencies. `tools/validate-fomod.py` checks that one-for-one - 16/16.
* Of the 251 options, 132 install recoloured files; the rest install nothing, and the 31 that would
  have installed something in Norden say so in their description ("Norden UI's own file for this
  option already matches"). Every option is kept so the screens you click are the screens you
  clicked in Norden.
* A dry install (`tools/install-with-choices.py`) of a 16x9 default run shows 15 steps, 84 options
  and **447 files** landing in `Interface`, `SKSE/Plugins/wheeler` and `MapMarkers`.

Point your mod manager at that folder (or zip it with `tools/build-package.py`), install it **after**
Norden UI, and pick the same options you picked there.

## Build

Needs Python 3.9+ and [JPEXS FFDec](https://github.com/jindrapetrik/jpexs-decompiler) (`ffdec-cli`).
On a machine without a system JVM, `pip install jdk4py` supplies one and `FFDEC` can point at a
two-line wrapper calling `java -Djava.awt.headless=true -jar ffdec-cli.jar` - that is how this build
was produced.

```bat
set FFDEC=C:\Program Files (x86)\FFDec\ffdec-cli.exe
set NORDEN_UI=D:\mods\Norden UI
set EDGE_UI=D:\mods\Edge UI
set EDGE_OUT=D:\mods\unpublished Norden UI - Edge Colours

python tools\export-xml.py                 :: Norden  -> build\xml
python tools\export-xml.py --edge          :: Edge    -> build\xml-edge   (optional but recommended)
python tools\sample-edge.py --write --svg  :: measure Edge's real palette
python tools\palette.py                    :: eyeball the mapping before committing to it
python tools\recolour.py --build           :: write the recoloured SWFs
set NORDEN_SVG_ALL=1 & python tools\recolour-svg.py --write
python tools\verify.py --svg               :: prove it on the shipped files
python tools\build-fomod.py --write      :: mirror Norden's installer onto the recoloured files
python tools\validate-fomod.py           :: prove the mirror, option for option
python tools\install-with-choices.py     :: dry-run the installer
python tools\build-package.py --verify
```

Install Norden UI first with the options you want, then this mod **after** (below) it, so its files
win. No plugin, no INI.

## Not covered by loose files

RaceMenu's race menu and bottom bar live inside `RaceMenu.bsa` and Character Progression Control's
level-up screen is its own mod; Norden restyles those through the Dynamic Interface Patcher at run
time. Recolouring them means shipping **deltas** as a DIP patch, never finished files, exactly as
NordenUIBlack does - not yet wired up here (see `CHANGELOG.md`).

## Credit and licence

Norden UI by Nithog, Edge UI by Eugene. All art is theirs; this repository only describes and
applies a colour mapping. Tools are GPL-3.0-or-later (`LICENSE`); see `NOTICE.md`.
