# Changelog

## 1.2.0 - the menus, measured by rendering them

Reported: 1.1.0 changed the text but not the menu bodies. Investigating exposed the flaw under every
measurement in this project - and then contradicted the premise.

* `tools/render-census.py` renders frame 1 of every menu both mods have and measures the visible
  pixels, after removing the SWF stage background (`#333333` in nearly every file of both mods; left
  in, the two read as identical at every percentile) and frames too small to be menus.
* **Node count is not screen area.** A panel is one colour node covering the screen, an icon is two
  hundred covering nothing - which is why every ramp came out as identity through 128-204.
* **Measured properly, the menu bodies already match**: median luminance gap 1 of 255 across 131
  menus. The outliers are real and run both ways - statsmenu 140 vs 48, trainingmenu_fill 101 vs 220.
* `palette.render_curve()` fits a monotone per-menu curve, applied only where the evidence supports
  it (28 of 131 menus). Elsewhere fills keep Norden's own values; the node-census ramp was moving
  panels that already matched and made 43 menus worse.
* **Stale art was shipping.** The build only writes files whose colours change, so 50 files the new
  rule no longer touches were still packaged from the previous build. Now deleted before packaging.
* `verify.py` recomputes every shipped file from Norden's original and demands an exact match - the
  old "every neutral is a ramp value" invariant died when leaving a fill alone became deliberate.
  850 of 850 pass, with 27% warm text.
* Closed loop: the shipped art is re-rendered and compared to Edge. 18 closer, 85 unchanged, 27
  marginally further. Four bugs were caught this way; all four are in `docs/census.md`.

## 1.1.0 - the colours actually change

Reported from the game: 1.0.0 showed none of Edge's gold or cream. Two causes, one a bug and one a
mistake in judgement.

* **Channel swap fixed.** JPEXS writes XML attributes alphabetically (alpha, blue, green, red) and
  the recolour substituted values positionally, swapping red and blue on every write. Invisible on
  greys, so every existing check passed; it turned 1.0.0's only warm output `#f5d87c` into `#7cd8f5`,
  a pale blue. Values are now substituted by name, with a selftest.
* **Colour-temperature transfer** replaces the flat ramp. Per menu and per node role, Norden's
  neutrals adopt the hue and saturation Edge uses there, at Norden's own luminance. The census had
  said it all along: 35% of Edge's text nodes are cream or gold against 5% of Norden's. `--flat`
  restores 1.0.0 behaviour.
* Pure white, near-black, Skyrim's status hues and the Scaleform masks are preserved deliberately.
* `verify.py` fails a build whose shipped text is not warm - the check whose absence let 1.0.0 ship.
  It caught the channel swap immediately (0% warm on the first 1.1.0 build).

## 1.0.0 - unreleased

First cut: Norden UI recoloured to Edge UI's palette.

* `tools/palette.py` - the shared rule: monotone piecewise-linear neutral ramp Norden -> Edge,
  neutral detection by channel spread, optional accent remap, alpha never touched. `--selftest`
  covers the invariants (monotone, endpoints pinned, grey order preserved, hues and status colours
  untouched, spread boundary).
* `tools/export-xml.py` - Norden and (with `--edge`) Edge to JPEXS XML.
* `tools/sample-edge.py` - measures Edge's real ramp and accent and writes the measured palette.
* `tools/recolour.py`, `tools/recolour-svg.py` - the SWF and SVG passes.
* `tools/verify.py` - re-exports the shipped SWFs and fails if any Norden neutral survived.
* `tools/build-package.py` - version-stamped zip.

### Measured, then built

* `palette/edge-ui.measured.json` - the mapping, derived from a census of both mods rather than from
  estimates. `docs/census.md` records the three findings that shaped it: the `#333333` both mods
  carry is the SWF stage background and not the panel; the most-used saturated colour in both is a
  Scaleform mask, not an accent; and the mods already share most of their neutral ramp, so the real
  differences are the dark-mid surfaces and the text accents.
* Built: 896 of 926 SWFs and 84 of 150 SVGs recoloured, 0 failures, `verify.py --svg` PASS.
* `tools/palette.py` gained `protected` colours and an explicit `accent_map`; `tools/sample-edge.py`
  became role-aware and now writes a reviewable proposal instead of the shipped palette.

### The installer

* `tools/build-fomod.py` rewrites Norden UI's own `ModuleConfig.xml` instead of inventing one, so the
  18 steps, 92 groups, 251 options, images and - critically - the 94 condition flags and 24 flag
  dependencies that hide and show whole pages are carried over untouched. Only two things change:
  sources with nothing recoloured are dropped (this mod is an overlay), and the names point here.
* `tools/validate-fomod.py` compares the result to Norden's option for option: 16/16 checks.
* `tools/install-with-choices.py` dry-runs the installer with flag evaluation. It caught two of its
  own bugs worth recording: Norden numbers every option ("1. Skip"), so a naive "skip the none
  option" rule kept choosing the opt-out; and the Wheeler pages are gated behind a flag set by an
  option that installs no files at all, so the Wheeler art was never being exercised.

### Fixed after 1.0.0 was pushed

The 1.0.0 push contained an installer and no art. `.gitignore` excluded `*.swf`, `*.svg`,
`Interface/` and `SKSE/` anywhere in the tree, and a negation cannot re-include a file that lives
inside an excluded **directory**, so `git add -A` skipped all 896 recoloured SWFs silently. Being
ignored, they were not preserved by the build sandbox either, so the pipeline was re-run from source
to recover them. The directory rules are now anchored to the repository root and the output tree is
re-included explicitly, and `Norden UI - Edge Colours.zip` (1092 files, 54.6 MB, `fomod/` at its
root) ships the same content as a Mod Organizer 2 installable archive.

Lesson kept in the ignore file itself: after a build, count what is *staged*, not what is on disk.

### Not done yet

* RaceMenu (race menu, bottom bar) as a DIP patch of deltas, the way Norden and NordenUIBlack ship
  it - the files are inside `RaceMenu.bsa` and must never be redistributed.
* Character Progression Control's level-up screen.
* A FOMOD mirroring Norden UI's own installer steps and options.
* An in-game pass through the installer itself. It is validated and dry-run, never clicked.
* In-game screenshots. Every claim here is measured off the files; nobody has looked at the result
  on a screen yet, and the near-white lift (`229 -> 235`) is the anchor most worth eyeballing.
* `palette/edge-ui.json` is kept only as the no-art fallback; the measured palette supersedes it.
