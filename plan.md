# Plan: 3D exercise library → fitness app + short-form content

## Goal

A library of short, looping 3D exercise animations: correct form, the worked muscles
highlighted (main red, secondary orange), real equipment (barbells, dumbbells, cables,
machines, benches). The same scenes feed:

1. **The app** (Expo / React Native, built later). Home screen = a front/back body
   where every muscle is tappable → list of exercises for that muscle (plus an "All"
   button) → exercise screen with the loop and a clear explanation.
2. **Short-form content** (TikTok / Reels / Shorts), built later from the same scenes.

**Current focus: the models and the animation pipeline.** No app code yet, but every
output must already match the app's asset contract (see "Delivery format").

## What already works (see handoff.md)

- MPFB2 body (CC0) with full fingers, driven by a rule-based pose solver.
- 17 muscle groups baked from Z-Anatomy onto the body skin as masks (front and back verified).
- Squat (correct form), cable triceps pushdown (moving cable + weight stack), dumbbell curl.
- Eevee renders: 3 exercises × 2-3 views × 72 frames in ~6 min on the M2 Pro.

## Two agents: who owns what

Both agents work in the same repo on `main`, in **separate directories**, committing
small and often (`git pull --rebase` before each commit). File ownership avoids conflicts:

| Area | Agent A: Motion | Agent B: Equipment, look and delivery |
|---|---|---|
| Directories | `core/solver.py`, `core/body.py`, `motion/`, `qa/` | `core/look.py`, `core/studio.py`, `core/render.py`, `equipment/`, `catalog/`, `bodymap/`, `dist/` |
| Specs | `motion/specs/<id>.json` (pattern + params) | `catalog/<id>.json` (name, muscles, equipment, cues, explanation) |
| Entry point | `build.py` (merges both specs by id, poses, renders) | export hooks called by `build.py` (`core/render.py`) |

Changing a file the other agent owns: leave a note in `handoff.md` → "Requests" and
let the owner make the change. `core/` interfaces (function signatures) only change by
adding, never by breaking.

## Exercise spec contract

`catalog/<id>.json` (Agent B):
```json
{
  "id": "barbell_back_squat",
  "name": "Barbell Back Squat",
  "equipment": ["barbell", "power_rack"],
  "primary": ["quadriceps", "glutes"],
  "secondary": ["adductors", "hamstrings", "lower back", "calves"],
  "level": "intermediate",
  "steps": ["..."], "cues": ["..."], "mistakes": ["..."], "breathing": "...",
  "source": "free-exercise-db:Barbell_Squat", "reviewed": false
}
```
Muscle names = the 17 groups in `core/look.py: GROUPS` (free-exercise-db names).

`motion/specs/<id>.json` (Agent A):
```json
{
  "id": "barbell_back_squat",
  "pattern": "stand_hinge",
  "params": {"stance": 0.17, "toe_out": 15, "depth": "parallel", "torso": 40, "bar": "high_back"},
  "props": [{"kind": "barbell", "attach": "hands", "grip_width": 0.5}],
  "tempo": {"hold_top": 6, "down": 31, "hold_bottom": 7, "up": 24, "hold_end": 4},
  "views": ["front", "side", "threeq"],
  "approved": false
}
```

## Phases

### Phase 0: foundation (Agent A first, ~half a day; Agent B meanwhile does B0)
- A0. `git init`, `.gitignore` (assets/za, assets/*.zip, assets/Z-Biomechanics*, review/,
  dist/, .blender-profile/, __pycache__). Keep `assets/maps/` in git (small, needed).
- A0. Split `common.py` into `core/body.py` (make_human), `core/solver.py` (Poser,
  frame_align, two_bone), `core/look.py` (GROUPS, masks, muscle_material),
  `core/studio.py` (lights, floor, cameras), `core/render.py` (render_views, video, sheet).
  Keep `common.py` as a thin re-export so old scripts still run.
- A0. `build.py <id> [--quick] [--views ...]`: one CLI for every exercise.
  Port squat, pushdown and curl to specs + patterns. Their renders must match today's
  (golden check: compare contact sheets by eye; keep them in `qa/golden/`).
- B0 (no core edits): build `catalog/` for the MVP list below from free-exercise-db
  (Unlicense) plus written explanations (steps, cues, common mistakes, breathing),
  `reviewed: false`. Start `bodymap/` research (see Phase 1).

### Phase 1: patterns + equipment basics
**Agent A**
- Pattern `stand_hinge`: squat variants, deadlift, Romanian deadlift, good morning,
  sumo squat, goblet squat. Hip-hinge path vs knee-dominant path as params.
- Pattern `split_stance`: lunge, reverse lunge, split squat, step-up.
- Pattern `arm_isolation`: curls (dumbbell, barbell, hammer, cable), pushdowns (bar,
  rope), overhead extension, lateral/front raise (shoulder abduction/flexion with the elbow soft).
- **Scapula/clavicle motion**: clavicle + shoulder01 bones follow arm elevation
  (upward rotation ~1:2 with the humerus above 30°), protraction/retraction for
  presses and rows. Needed before any press or pull looks right.
- Hand contact: two hands on one rigid bar (bar defines both wrist targets),
  grip widths, grip types (over/under/neutral/mixed).

**Agent B**
- Equipment: barbell + plates (Olympic, plates by kg), EZ bar, kettlebell, flat /
  incline / decline bench, power rack with J-hooks, pull-up bar, dip station, mat,
  resistance band (curve between two anchors, stretches with distance).
- Cable tower variants: high / mid / low pulley, dual cable crossover, handles
  (rope, D-handle, V-bar, lat bar, ankle strap). Fix: pushdown cable angle (pulley
  sits right above the bar path; the user stands closer).
- Look: fix the muscle-detail normal map (left/right tangent split, ecorche face;
  probably mirrored-UV tangent sign, or bake in object space and convert), then decide
  if it ships. Highlight edge softness, base colour, light background tuned for the app.
- **Delivery format v1** (below): ffmpeg encode step, poster frames, manifest.

### Phase 2: harder patterns + machines
**Agent A**
- Pattern `lying`: bench press (barbell / dumbbell), flyes, skull crushers, lying leg
  raise; body contact with the bench (pelvis, upper back and head pinned, feet planted).
- Pattern `seated`: lat pulldown, seated cable row, leg press, leg extension, leg curl,
  chest press, pec deck, seated dumbbell press.
- Pattern `hang_support`: pull-up, chin-up, dips, hanging knee raise.
- Pattern `floor`: push-up, plank, side plank, crunch, glute bridge, hip thrust (bench),
  bird dog, superman, mountain climber.
- Pattern `overhead_press` + `row` (bent-over, one-arm dumbbell row, inverted row).
**Agent B**
- Machines (frame + one moving part each, driven from the hand/foot position like the
  cable tower): lat pulldown, seated row, leg press (sled on rails), leg extension,
  leg curl, chest press, pec deck, Smith machine, hack squat.
- Seat/pad contact points exported for Agent A's `seated`/`lying` patterns
  (a small dict per machine: seat height, back pad plane, foot plate, handle path).

### Phase 3: quality gate + MVP batch
**Agent A**
- `qa/check.py`: joint limits per bone, planted-foot slide, hand-to-implement gap every
  frame, loop closure (frame 1 == last), self-intersection spot checks (hands vs thighs),
  balance (centre of mass over the support base). Fails keep an exercise out of `dist/`.
- Micro-motion so loops read less mechanical: subtle weight shift, breathing, head
  settle, eased tempo variation; never changes the form.
**Agent B**
- `bodymap/`: home-screen body (see "Body map") front + back.
- Batch build of the MVP list → `dist/` + `dist/manifest.json`.
- Review page: `review/index.html` with every loop + its spec + muscle list, so the
  user (and later a trainer) can approve exercises; approval writes `approved: true`.

### Phase 4 (later, not now): app + short-form content
- Expo app: body map home → muscle list (+ "All") → exercise screen (loop + steps,
  cues, mistakes). Feed-style vertical scrolling of exercises.
- Short-form: 1080×1920 renders from the same scenes + voiceover, reusing the existing
  video pipeline in `~/Coding/video-edit-automation`.

## MVP exercise list (30, covers every pattern and equipment type)

Bodyweight: bodyweight squat, push-up, plank, glute bridge, lunge, crunch, pull-up, dips.
Dumbbell: dumbbell curl, hammer curl, lateral raise, shoulder press, one-arm row, goblet squat,
Romanian deadlift (DB).
Barbell: back squat, deadlift, bench press, overhead press, bent-over row.
Cable: triceps pushdown (bar), rope pushdown, cable row, lat pulldown, cable crossover, face pull.
Machines: leg press, leg extension, leg curl. Kettlebell: kettlebell swing.

## Delivery format (app contract)

Light and smooth on phones: **pre-rendered video loops, not real-time 3D** (GLB is an
optional extra later, e.g. for an orbit view).

Per exercise in `dist/<id>/`:
- `loop_<view>.mp4`: H.264 (+ HEVC variant), 720×900 (4:5), 30 fps, one rep
  (~2.4 s), seamless loop, no audio, target ≤ 400 KB. Background = app light background
  colour (one constant in `core/studio.py`); dark variant later.
- `poster_<view>.webp`: first frame, ≤ 40 KB, shown while the video loads.
- `thumb.webp`: 320 px square, for lists.
- `dist/manifest.json`: `[{id, name, primary, secondary, equipment, views, files, duration, approved}]`,
  generated from `catalog/` + `motion/specs/` + QA results.
- For TikTok later: same scene re-rendered at 1080×1920, not upscaled.

## Body map (home screen)

Same MPFB body, front + back, neutral pose, rendered flat with the app's style. Tappable
regions come from the baked masks: render an ID pass (each of the 17 groups a flat
unique colour, no lighting), trace each colour into SVG paths (OpenCV contours or
potrace, simplified), output `bodymap/front.svg`, `bodymap/back.svg` with
`<path data-muscle="quadriceps" ...>` plus `front.webp`/`back.webp` underlay.
React Native later draws it with `react-native-svg`.

## Definition of done (per exercise)

1. Spec in both `catalog/` and `motion/specs/`.
2. `qa/check.py` passes.
3. Contact sheet + loop reviewed by the user (form), `approved: true`.
4. Files in `dist/` within the size budget, manifest entry present.

## Risks

- Form correctness: the solver enforces rules, but every exercise still needs a human
  form check (the user, later a trainer). Health content: treat like the tinnitus content.
- Licences: Z-Anatomy masks are CC BY-SA → credit in the app's About screen, mask files
  stay CC BY-SA. MPFB assets CC0. CMU/Mixamo files must never be redistributed (videos ok).
  Don't use SMPL/AMASS-based models or data; Tencent HY-Motion is banned in the EU.
- Disk: the Mac has ~42 GB free. Delete old frame folders in `review/` after encoding.
