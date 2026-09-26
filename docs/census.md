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


## 1.2.0 - measuring the menus the way the player sees them

1.1.0 warmed the text and the player reported the menu bodies unchanged. Chasing that exposed the
methodological error under every census in this repository, and then contradicted the premise.

### Node count is not screen area

Every census here counted colour NODES in the SWF XML. A panel background is one node covering the
whole screen; an icon is two hundred nodes covering nothing. Counted by node the two mods "share"
the mid greys - which is exactly why every ramp came out as identity through 128-204 and the menu
bodies never moved.

`tools/render-census.py` renders frame 1 of every menu both mods have and reads the visible pixels.
Two artifacts had to go first:

* **The SWF stage background.** Both mods declare `#333333` in nearly every file. Left in, it swamps
  the histogram and both sides read as identical at every percentile - and it produced a wrong
  conclusion I nearly shipped: Norden's crafting menu appears to render as flat mid-grey, but that
  grey IS the stage (`#999999` there), which Scaleform never shows in game. It is now read from the
  SWF's SetBackgroundColor tag, straight from the binary, so the census does not need the XML export.
* **Frames too small to be a menu** (under 500 visible pixels) - icons and empty shells.

### The surprise: the menu bodies already match

Across the 131 menus measurable on both sides, the **median luminance gap between Norden and Edge is
1** (of 255). The real gaps are a minority and run in both directions:

| menu | Norden | Edge |
| --- | --- | --- |
| statsmenu | 140 | 48 |
| craftingmenu | 163 | 90 |
| inventorylists_select_lr | 146 | 82 |
| trainingmenu_fill | 101 | 220 |
| lockpickingmenu_fill | 85 | 191 |

### What 1.2.0 does, and what it deliberately does not

A monotone curve is fitted per menu by quantile matching between the two rendered distributions, and
applied only where there is evidence: the menu was rendered on both sides, the median gap is over 25,
and the value lies inside the range the render covers. That is **28 of 131 menus**. Everywhere else
the fills keep Norden's own values - including against the neutral ramp, which the renders showed was
making 43 menus worse.

Closed-loop check (re-render the shipped art, compare to Edge): 18 menus closer, 85 unchanged, 27
marginally further, mean gap unchanged. An honest wash overall with a clear win on the statsmenu
family - which is why the rule is gated rather than global.

### Four bugs the closed loop caught

* **Clamping.** Quantile mapping applied to a colour absent from the rendered frame lands at
  quantile 0 or 1 and is pinned to the end of Edge's distribution. In `itemcard_thumb`, where both
  mods render identically, every dark node became 153 and a menu matching Edge exactly (254) shipped
  at 41.
* **Domain mismatch.** The curve was looked up with the *ramped* luminance while its domain is what
  Norden *renders*, so menus needing lightening were darkened - `itemcard_*_bg` sat at 27 against
  Edge's 31 and came out 16.
* **An artifact in the checker itself.** It removed the stage background using Norden's colour, but
  our build recolours the stage too (51 -> 41), so those pixels stayed in and every menu read as 41.
  The first "everything got worse" verdict was the checker, not the build.
* **Stale art shipping.** The build only writes files whose colours change, so when the
  evidence-only rule stopped changing 50 files, the previous build's SWFs stayed in the output folder
  and went into the archive. `verify.py` now recomputes every shipped file from Norden's original and
  demands an exact match; stale files are deleted. The same failure recurred one level up - the
  repository kept the 1.1.0 archive after the 1.2.0 art was pushed - which is why the archive is now
  rebuilt and pushed in the same commit as the art it contains.

### The honest limit

Norden UI and Edge UI are different art. Their menu chrome already renders within a luminance level
or two of each other; what differs is shape, layout and the elements each mod draws that the other
does not. A recolour can carry Edge's palette - its cream and gold text, its darker stats and
crafting panels - but it cannot turn one mod's menus into the other's.
