# The colour census, and why the mapping looks the way it does

Measured on 2026-09-24 with JPEXS FFDec 26.x against the two mods as shipped:

| | files | colour nodes | distinct colours |
| --- | --- | --- | --- |
| Edge UI 0.61 | 321 SWF | 20 034 | 389 |
| Norden UI | 926 SWF + 150 SVG | 84 935 | 1 124 |

Reproduce with `tools/export-xml.py` (both mods) then `tools/sample-edge.py --svg`.

## Finding 1 - the stage background is not the panel

Edge carries the neutral **51 (`#333333`) in 303 of its 321 files**, which reads like a grey-panelled
UI. It is not: 291 of those occurrences are `backgroundColor`, the SWF **stage** colour, which
Scaleform does not paint in game. Edge's painted surfaces are `color` nodes, and those are
overwhelmingly **0 (`#000000`)** - 12 774 nodes across 101 files.

Norden is the same story (772 of its 51s are `backgroundColor`), which also corrects a premise this
repository started from: Norden's panels are **not** `#333333`. Both mods paint black panels and
lean on alpha.

So the census counts painted nodes only (`neutrals(..., painted_only=True)`).

## Finding 2 - the naive "accent" is a mask

Ranked by raw usage, Edge's most-used saturated colour is **`#00ff00`** (124 nodes, 51 files) and
Norden's is the same (736 nodes, 172 files), with `#00ffff` close behind. These are Scaleform
mask / colour-transform placeholders that are replaced at run time; recolouring one breaks the
effect it drives. They are excluded from accent ranking **and** listed in `protected` so `map_rgb`
never touches them.

With masks dropped and `textColor` weighted up, Edge's real accent family appears:
**`#ece2b7`, `#f5d87c`, `#aaa07a`, `#b1af97`, `#f6db85`** - the cream-and-gold text that is Edge's
signature.

## Finding 3 - the two mods already agree on most of the ramp

Painted neutrals by surface weight:

* Edge: `0`, `255`, `204`, `153`, `102` (plus sparse `14`, `26`, `191`, `203`, `211`)
* Norden: `0`, `255`, `204`, `229`, `88`, `169`, `153`, `230`, `235`, `25`, `48`, `102`, `16`

And these hued colours are **byte-identical in both** - vanilla/SkyUI inheritance, so they are left
alone: `#0032aa`, `#280c02`, `#803300`, `#9d0000`, `#00cc66`, `#641601`.

The genuine differences are:

1. **The dark-mid range.** Norden paints surfaces at `25`, `48`, `88`; Edge at `0`, `51`, `102`.
   Edge is the higher-contrast UI. This is the main thing the recolour moves.
2. **Text accents.** Norden uses `#ffd700` gold and `#4dad4f` green; Edge uses the cream/gold
   family. `accent_map` maps `#ffd700 -> #f5d87c` and `#ffd800 -> #f6db85`. Norden's green is left
   alone by default: Edge has no green text to map it onto, and `#00cc66` already exists in both.

## The shipped mapping

`palette/edge-ui.measured.json` is curated from the census rather than emitted by it. Anchors:

```
0 -> 0     16 -> 8     25 -> 13    45 -> 34    48 -> 38    88 -> 72    102 -> 92
128 -> 128    153 -> 153    169 -> 169    204 -> 204    229 -> 235    235 -> 240    255 -> 255
```

Dark-mid greys are pulled down toward Edge's `0`/`51`/`102`; the range both mods share
(`128`-`204`) is identity; Norden's near-white text lifts slightly toward Edge's brighter text.

`tools/sample-edge.py --write` emits its own proposal to `palette/edge-ui.proposed.json`. With the
Edge target limited to its six real tones it produces `25 -> 10`, `88 -> 66`, `169 -> 159` - the same
direction and nearly the same magnitude as the curated anchors, which is the cross-check that the
curated ramp is not hand-waving. It is kept as a separate file because a nearest-snap over Edge's
*full* ramp lightens some mid greys, pulled up by sparse noise values (`191`, `203`, `211`), and
because snapping every neutral onto six values would band Norden's gradients. A piecewise-linear
curve keeps gradients smooth.

## What the recolour actually changed

896 of 926 SWFs and 84 of 150 SVGs. The largest movements:

```
#e5e5e5 -> #ebebeb  x4865      #333333 -> #292929  x1076
#585858 -> #484848  x2607      #303030 -> #262626  x813
#e6e6e6 -> #ececec  x1135      #191919 -> #0d0d0d  x665
#ebebeb -> #f0f0f0  x828       #ffd800 -> #f6db85  x400
```
