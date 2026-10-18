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

Both the old tangent normal and mask-derived bump detail are disabled by default.
The generated height map is retained only for opt-in experimentation; its broken
surface outlines must not be used as anatomical detail in delivery renders.
