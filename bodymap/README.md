# Baked-mask body selector

`front.svg` and `back.svg` are 720×900 neutral MPFB body selectors. Each SVG uses
its adjacent WebP as the underlay, with transparent `<path data-muscle="…">` hit
regions. Paths include accessible names and keyboard focus. The review page
handles Enter/Space and clicks; React Native can use the same paths with
`react-native-svg` and supply the WebP separately.

All 17 catalog muscle groups occur across the two views, as recorded in
`coverage.json`. Some small visible regions (especially abductors on the back)
are difficult to tap at phone size, so retain a labelled muscle list and “All”
control. Do not enlarge a region by inventing anatomy. Groups with no matching
MVP exercise should show an empty state.

Regenerate from the repository root after changing the baked UV masks:

```sh
BLENDER_USER_RESOURCES="$PWD/.blender-profile" /Applications/Blender.app/Contents/MacOS/Blender -b --python bodymap/render.py
python3 bodymap/trace.py
```

The second command requires NumPy and Pillow. The renderer creates a neutral
underlay and a flat unique-colour ID pass for each view. At a visible surface
point the strongest mask wins, above a 0.3 threshold. The tracer follows pixel
boundaries, preserves holes using even-odd filling, removes components smaller
than 12 pixels, and simplifies boundaries with a 1.1 px tolerance. These are
projections of the baked masks, not manually drawn muscle outlines.

Retain `LICENSE.md` with the SVGs, masks and derived media.
