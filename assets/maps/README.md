# Muscle maps and relief

The six RGB masks contain the 17 muscle groups in `core/look.py:GROUPS` order.
Source fitting and baking are described in `research/FINDINGS.md` and
`build_muscle_maps.py`. Source anatomy attribution is in `LICENSE.md`.

The old tangent-space `muscle_normal.png` had a mirrored left/right seam and
excessive face relief. It is intentionally ignored by git and never sampled by
the current shader. The shipping detail uses a shallow height bump derived from
the masks (`muscle_detail_height.png`), excluding the face/neck. This keeps the
neutral mannequin readable without the faulty tangent bake.

`python3 core/prepare_maps.py` creates the softened masks under `soft/` and the
height map. It requires Pillow. The shader prefers softened masks and falls back
to the original masks if they are absent. The current shader uses a 1.5 mm bump
distance at 0.24 strength. These settings are visual relief, not anatomical depth.

The deltoid channel was rebaked from the fitted muscular source to improve its
coverage. To reproduce that bake, start with the unmodified fitted scene:

```sh
BLENDER_USER_RESOURCES="$PWD/.blender-profile" /Applications/Blender.app/Contents/MacOS/Blender -b review/muscle_fit.blend --python core/rebake_shoulders.py
python3 - <<'PY'
from PIL import Image
p = 'assets/maps/mask_3.png'
r, g, b = Image.open(p).convert('RGB').split()
shoulder = Image.open('review/shoulder_projection.png').convert('RGB').getchannel('R')
Image.merge('RGB', (r, g, shoulder)).save(p)
PY
python3 core/prepare_maps.py
```

The rebake extends only the distal deltoid fit, then projects all source groups
with the others acting as occluders. Do not rerun it on an already modified source
scene. Re-render exercise extremes and the body selector after changing masks.
