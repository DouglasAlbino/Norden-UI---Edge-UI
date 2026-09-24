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

Default anchors (`palette/edge-ui.json`): `#333333 -> #141414`, `#404040 -> #1a1a1a`,
`#585858 -> #262626`, `#666666 -> #2e2e2e`, `#e0e0e0 -> #e2e2e2`, black and white pinned.
`python tools/palette.py` prints the full table; `--selftest` checks the invariants.

The defaults are a fallback. `tools/sample-edge.py` measures Edge UI's **real** ramp and accent from
an installed copy, pairs it rank-by-rank with Norden's measured ramp, and writes
`palette/edge-ui.measured.json`, which every tool then prefers automatically.

## Tools

| file | what it does |
| --- | --- |
| `tools/export-xml.py` | every Norden SWF to JPEXS XML (`ffdec-cli -swf2xml`) in `build/xml`; `--edge` does the same for Edge UI into `build/xml-edge` |
| `tools/sample-edge.py` | censuses Edge's colours, derives its ramp and accent, `--write`s `palette/edge-ui.measured.json` |
| `tools/palette.py` | the rule itself: `map_rgb`, the ramp, the selftest |
| `tools/recolour.py --build` | remaps every colour node in Norden's XML and `-xml2swf`s the changed files into the output mod folder |
| `tools/recolour-svg.py --write` | the same rule on Norden's Wheeler SVGs, with read-back |
| `tools/verify.py` | re-exports the **shipped** SWFs and proves no Norden neutral survived |
| `tools/build-package.py` | stamps `VERSION`, adds `dist/README.txt`, zips the installable archive |

## Build

Needs Python 3.9+ and [JPEXS FFDec](https://github.com/jindrapetrik/jpexs-decompiler) (`ffdec-cli`).

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
