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
