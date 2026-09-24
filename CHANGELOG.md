# Changelog

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

### Not done yet

* RaceMenu (race menu, bottom bar) as a DIP patch of deltas, the way Norden and NordenUIBlack ship
  it - the files are inside `RaceMenu.bsa` and must never be redistributed.
* Character Progression Control's level-up screen.
* A FOMOD mirroring Norden UI's own installer steps and options.
* Anchors in `palette/edge-ui.json` are hand-set from Edge UI's documented values; replace them with
  `tools/sample-edge.py --write` output before any release.
