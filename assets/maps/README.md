# Muscle masks

The six RGB atlases contain the 17 groups in `core/look.py:GROUPS` order.
The original selected-to-active ray bakes remain at `mask_0..5.png` for comparison.
Their fitted Z-Anatomy sources and attribution are described in `LICENSE.md` and
`build_muscle_maps.py`.

Shipping masks are now projected from the nearest fitted muscle surface onto the
MPFB skin, then smoothed along connected skin vertices. This avoids holes caused
by bones/other source objects blocking bake rays, and does not blur across separate
UV islands. Face, hands, feet and anterior shin remain neutral. Source-distance
limits and regional bounds prevent arbitrary distant muscles filling empty skin.
These are group-level surface highlights, not an exposed-muscle anatomical model.

Reproduce from the original fitted scene:

```sh
BLENDER_USER_RESOURCES="$PWD/.blender-profile" /Applications/Blender.app/Contents/MacOS/Blender -b review/muscle_fit.blend --python-exit-code 1 --python core/repair_muscle_maps.py
python3 core/prepare_maps.py
```

`repaired/` contains the new atlases and vertex coverage counts; `soft/` is the
shader input. Re-render `bodymap/render.py`, run `bodymap/trace.py`, and rebuild
exercise deliveries after changing these maps. All derivatives retain CC BY-SA
attribution. No external assets were added for this repair.

## Continuous surface detail

The old tangent normal and raised-mask `muscle_detail_height.png` remain unused.
The default shader now reads `surface_detail_height.png`, a 16-bit scalar map
constructed on connected skin vertices by `core/surface_detail.py`:

- Identify connected muscle components in the existing fitted Z-Anatomy meshes.
- Project their identity to the same skin used for the group masks; remove tiny
  fragments and compute distances along connected skin edges to muscle boundaries.
- Form rounded bellies over a 35 mm transition and smooth on the surface before
  baking. UV seams never enter the distance calculation.
- Exclude face/neck, hands, feet and anterior shin. No extra mesh or displacement.

The bump uses 0.004 m distance at 0.5 strength, with low-contrast (±6%) shading
within anatomy regions. This is a restrained visual cue, not measured anatomical
muscle depth or a fibre simulation. `use_normal=False` produces the plain surface.
The existing repair command above regenerates both masks and the new detail map.
`prepare_maps.py` only softens group masks and builds the unused legacy height map;
it does not overwrite the new surface relief.

Highlight weights are sharpened and normalized as one surface partition. Active
neighbouring groups are summed before mixing with the grey base, so two half-weight
muscle masks do not create a grey seam. Primary and secondary colours blend within
that covered region. Neutral regions stay neutral; no UV dilation is used.

Validation and comparisons:

```sh
BLENDER_USER_RESOURCES="$PWD/.blender-profile" /Applications/Blender.app/Contents/MacOS/Blender -b --python-exit-code 1 --python qa/check_surface_layer.py
BLENDER_USER_RESOURCES="$PWD/.blender-profile" /Applications/Blender.app/Contents/MacOS/Blender -b --python-exit-code 1 --python core/preview_surface.py
```

The first command renders synthetic primary/secondary boundaries and checks all
1,122 duplicated UV-seam vertices. The current maximum height discrepancy is
0.009616 on a 0–1 map (under 0.02 mm at the effective bump scale). The second makes
`review/surface_revision/index.html`, with identical-pose before/after comparisons
and neutral front/back relief previews. All 17 bodymap regions remain present.
