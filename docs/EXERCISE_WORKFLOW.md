# Updating and adding exercises

Run commands from the repository root. `python3 exercises.py --help` lists commands.
The source of truth is `catalog/<id>.json` (instructions/muscles/equipment) plus
`motion/specs/<id>.json` (motion, props, cameras and tempo). Keep IDs stable: apps and
media paths will use them. Match a new exercise to an existing motion pattern first.

## Change an existing exercise

```sh
python3 exercises.py revise dumbbell_shoulder_press --note "Lower shoulders in the starting position"
# Edit catalog/dumbbell_shoulder_press.json and/or motion/specs/dumbbell_shoulder_press.json.
python3 exercises.py validate dumbbell_shoulder_press
python3 exercises.py preview dumbbell_shoulder_press
# Inspect review/dumbbell_shoulder_press_sheet.png: pose, grip, equipment and highlights.
python3 exercises.py render dumbbell_shoulder_press
python3 core/review_server.py 8765
```

Open http://127.0.0.1:8765/review/index.html, check every view and the instructions,
then approve that version. The original approval history remains in Git under
`approvals/`. Reopening or changing an exercise does not overwrite that history.
Preview is only a small set of frames; rendering runs full motion QA and exports
all declared views to 720×900 H.264/HEVC loops, posters and a thumbnail.

Prefer spec parameters over changes to shared motion code for exercise-specific
adjustments. Shared code changes invalidate the library's render fingerprint;
finish edits first, then refresh once using:

```sh
python3 core/run_mvp.py --first dumbbell_shoulder_press
```

This resumes safely, skips current assets and audits the catalog. Check
`review/run_status.json` for completion. Do not edit rendering code during a batch.
Generated frames are deleted after encoding. If you need a before/after comparison,
copy the old contact sheet before previewing; it is replaced on each build.

## Add an exercise

```sh
python3 exercises.py new wide_push_up --from push_up --name "Wide Push-up"
```

This creates both JSON files with approval off. It copies motion parameters and
muscle/equipment tags as a starting point, and leaves TODOs for instructions and
source provenance. Replace every TODO; check inherited tags, bench angle, hand
contacts, range of motion, views and QA settings. Do not claim the template's source
as the source of a different exercise. Confirm licences before using external data
or assets; prefer procedural equipment. Then validate, preview, render and review
using the same commands as above. Unsupported movements need a new pattern in
`motion/patterns/`; unsupported equipment needs geometry and contact metadata.

There is no fixed 30-item limit. The catalog drives batch rendering, review and
manifest validation. New drafts have no delivery and cannot be approved yet.

## Check status and release

```sh
python3 exercises.py status
python3 exercises.py audit
```

Statuses distinguish current approvals, delivered versions needing review, and
missing/stale builds. Approval is tied to spec, pipeline and delivered-media hashes.
Changing those requires review again, even if an old JSON boolean is still true.
Unchanged deterministic re-exports can retain their approval. Failed/stale assets
cannot be approved. Approval does not launch rendering.

For explicit human approval given outside the review page:

```sh
python3 exercises.py approve dumbbell_shoulder_press --reviewed --note "Reviewed all views and instructions"
# Only after explicit approval of every current exercise:
python3 exercises.py approve --all --reviewed --note "Reviewed the full current library"
```

These commands must not be run to infer approval or bypass human review. Batch
approval preflights every selected delivery before changing any flags. Test the
workflow with `python3 -m unittest core.test_delivery core.test_workflow`.

Commit source, catalog, specs and `approvals/` records. `dist/`, render scenes and
third-party source assets are ignored by Git: preserve approved release bundles
separately, including manifest and attribution notices. Keep the project-local
`.blender-profile` and source maps available for regeneration. Git alone is not a
backup of the generated media or the Blender environment.


## Release rendering resources

After rendering, check that this project's Blender, ffmpeg, build and batch
processes have exited. Let necessary exports and the final audit finish; do not
leave redundant renders running. If a run is obsolete or cancelled, stop its
specific process group, preserve completed exports, and mark the runner status
accurately so the review page does not claim it is still working. Never kill all
Blender/Python processes indiscriminately: other applications may own them.
Keep the idle review server only while it is useful for review. Headless Blender
exits after each build and run_mvp.py exits after the final audit.

## Dark clothing look review (before the model delivery migration)

The app's `bg.video` is exactly sRGB `#0A0A0C`. The studio converts it to linear
shader values, disables dithering and uses an unlit matching floor. Procedural
compression shorts copy the body's UVs and deform weights; the female sports top
uses the same method. Covered muscles retain the shared highlight material.
No external clothing asset is required. The existing anatomy attribution applies.

Use the isolated look-preview mode while the two-exercise appearance review is pending:

```sh
python3 build.py bodyweight_squat --model male --look-preview --quick --frames 1,40
python3 build.py bodyweight_squat --model female --look-preview --quick --frames 1,40
python3 build.py dumbbell_shoulder_press --model male --look-preview --quick --frames 1,30
python3 build.py dumbbell_shoulder_press --model female --look-preview --quick --frames 1,30
```

Preview scenes, sheets and QA reports use `<id>_<model>` in `review/`. Omit `--quick`
for a review video. Every preview runs the existing all-frame motion QA; failure
returns a nonzero exit code. Preview mode cannot export to `dist/` or grant approval.
Female delivery/approval migration is the next phase, after the look review. These
local preview names do not yet change the app's content envelope.

Reviewing this sheet approves only the proposed appearance. Every rebuilt exercise
and model still needs its full delivery QA and explicit human approval. Do not run
the full library batch until the user has reviewed the two-exercise sheet.

Garment checks (`qa/check_clothes.py`, run inside each saved Blender preview) verify
copied UVs/rig groups and sample vertices and face centres over all 72 frames. Skin
fully beneath the garments is hidden by a rest-space shader mask; geometry remains
intact for motion QA. The check reports raw overlap and measured existing body-fold
contact separately, failing when clothing adds more than 2 mm beyond that contact.
This is a geometry check, not proof of visual quality: inspect the seams, folds and
highlight continuity in the sheet before accepting the appearance.

### Appearance revision 2: shorter clothing, hair, alpha stills

`core/clothes.py` now shares the curved hem and bra-boundary functions between
mesh cutting and skin occlusion. Side openings expose more upper thigh while the
centre preserves groin coverage. Fabric has its own muted highlight colours;
only the exercise's active groups tint it. The female top is cropped with narrower
straps. `core/hair.py` builds original hair and follows the existing head bone.
Both modules participate in the pipeline fingerprint, invalidating old approvals.

After the four existing look previews pass, run the unpublished comparison studies:

```sh
BLENDER_USER_RESOURCES="$PWD/.blender-profile" /Applications/Blender.app/Contents/MacOS/Blender -b --python-exit-code 1 --python core/appearance_studies.py
python3 core/appearance_review.py
```

Open `/review/look_v2/index.html` on the local review server. It includes true-alpha
PNG/WebP previews on switchable light/dark backgrounds and solid/inactive versus
muted/active bra material close-ups. The chest close-up is a material study, not
an exercise muscle classification. Studies never save or approve exercise scenes.
Hair loop closure and opaque fabric are checked; alpha channels are inspected.
Exercise video delivery retains the dark H.264 default, as documented in the app's
MVP Requests section. No full-library render before the revised appearance review.
