# 3D exercise library: open-source research (2026-10-15)

Goal: short looping 3D clips of gym + home exercises (barbell, dumbbell, cable,
machines, bodyweight), proper movement, correct muscles highlighted. Reused for
a TikTok-style app feed and for social videos.

## Verdict per layer

| Layer | Best free option | Status |
|---|---|---|
| Body | MPFB2 (CC0 assets, rigged, CMU-compatible rig) | works, tested |
| Muscle shapes | Z-Anatomy (CC BY-SA 4.0, ~900 separate muscles) | works static; not rigged |
| Which muscles per exercise | free-exercise-db (Unlicense): 876 exercises, 17 muscle groups, equipment field | data only |
| Motion, gym w/ equipment | **nothing free + commercial exists** | gap |
| Equipment | no CC0; CC-BY on Sketchfab (dumbbell, bench, leg press, smith, lat pulldown, pull-up bar) | build procedurally |

## Prior art: AssiamahS/opengym3d (MIT, ~12 stars, active 2026)
Same plan as ours: MPFB2 + mocap retarget -> animated GLB + muscle highlight,
headless Blender in CI, Three.js viewer. Useful code to borrow:
`pipeline/qa_glb.py` (joint/foot-slide/hand-to-implement QA),
`pipeline/video_mocap.py` (phone video -> MediaPipe -> motion),
`pipeline/build_exercise.py` (aim+roll retarget, procedural props).
Weak spots seen in their renders: highlights are crude skin-weight bands, no
equipment visible even on curls/deadlifts, their Z-Anatomy ecorche tears apart
when bound with bone weights (665 non-manifold islands).

## Motion sources and licences
- CMU mocap: may be used inside commercial products; may NOT redistribute/resell
  the files, even converted. Videos + app = fine. (Earlier note saying "any use" was wrong.)
- Mesh2Motion human packs: CC0, but only Pushup, Jumping Jacks, Crawl are fitness.
- Mixamo: ~20 fitness clips; use in projects yes, redistribute files no.
- Paid packs (check each licence): Fab "Gym Animation Pack" (27, with props incl.
  cable bar), Fab "Machine Workout Animations 96" (53 cable-bar), itch.io
  "Workout Animations Part 2" (300, $20), Unity "Power Gym Training" (33).
- Own capture: MediaPipe (Apache, single camera, weak depth; side view best),
  FreeMoCap (AGPL tool, multi-camera, data is yours), Move.ai (paid, best single-cam).
- Rejected: AMASS/HumanML3D/Motion-X/Fit3D/FLAG3D (non-commercial), GVHMR/WHAM/SMPL
  (non-commercial), Bandai Namco + LAFAN1 (NC-ND).
- Text-to-motion: MotionGPT / MoMask code is MIT but weights trained on
  non-commercial AMASS data. Tencent HY-Motion 1.0 licence excludes EU, UK and
  South Korea entirely, outputs included.

## Muscle simulation (not needed for v1)
MyoSuite / myo_sim / musclemimic (Apache 2.0, MuJoCo, 416-muscle full body) can
compute muscle activations from motion; research-grade. OpenSim (Apache).
MuSkeMo has no licence -> unusable. OpenCap (Apache code) = 2 phones -> OpenSim.

## Approaches to the muscle look
1. Bake Z-Anatomy muscle outlines onto the MPFB skin as per-muscle masks:
   anatomically shaped highlights on a body that deforms cleanly. Lowest risk.
2. Surface Deform: bind Z-Anatomy superficial muscles to the MPFB skin (not to
   bones) -> moving ecorche. Needs Z-Anatomy fitted to MPFB proportions first.
Either is a derivative of Z-Anatomy -> credit + share-alike on those assets.

## Equipment plan
Procedural in Blender, one rig per equipment type: dumbbell, barbell+plates,
EZ bar, kettlebell, bench (flat/incline), bands, pull-up bar, cable station
(pulley + curve to the handle + weight stack driven by handle travel), then
machines with one pivot/slider each (leg press, lat pulldown, chest press,
leg extension/curl). Hands IK'd to handles + grip pose; QA hand-to-implement gap.

## Feasibility test results (2026-10-15)

Built: `common.py` (body, pose solver, muscle material, studio), `build_muscle_maps.py`,
`squat_proper.py`, `arm_exercises.py` (pushdown | curl), `equipment.py`, `check_muscles.py`.

- Muscles: Z-Anatomy fitted onto MPFB per body segment (thigh, shin, arm, forearm,
  torso, head), torso depth refitted to the measured skin (Z-Anatomy torso ~27% deeper),
  then Cycles selected-to-active bakes -> assets/maps/mask_0..5.png (17 free-exercise-db
  groups, 3 per RGB image). Front + back read as textbook anatomy. Bake ~6 min.
  Gotchas: join the ~770 source meshes per group first (per-object ray casts made one
  map take 10 min); trunk muscles must be forced to the torso segment (off-centre
  centroids got fitted with the A-posed arm); "tensor fasciae latae" trips a "fascia" filter.
  Baked tangent normal map (muscle detail) splits L/R and gives an ecorche face -> off.
- Motion: rule-based solver, no mocap. Feet planted, hips on a path, two-bone limbs with
  the knee/elbow forced toward a hint, forearm twist set by a target palm direction.
  Pass the planned elbow as the pole or it drifts at deep flexion.
- Equipment: procedural dumbbell, straight bar, cable tower (two pulleys, poly-curve
  cable re-keyed per frame, top plates ride the cable length change).
- Render: Eevee 720x1280, 3 exercises x 2-3 views x 72 frames in ~6 min total.

Open items: muscle-detail normal map (tangent split), scapula/shoulder motion for
presses/rows/pull-ups, finger contact QA, bench/seat/hanging contact patterns,
micro-motion (weight shift, breathing) so loops read less mechanical.

## Pulldown form reference (2026-10-20)

Checked the wider-grip revision against primary coaching sources:
- ACE, Seated Lat Pulldown: https://www.acefitness.org/resources/everyone/exercise-library/158/seated-lat-pulldown/
- NASM, The Biomechanics of the Lat Pulldown: https://www.nasm.org/resource-center/blog/training/the-biomechanics-of-the-lat-pulldown-muscles-grip-and-form

Both describe a controlled pull toward the upper chest with a modest backward lean,
a braced torso, and no additional backward swing during the pull. The animation uses
an 18-degree stable lean and 92 cm hand spacing (previously 80 cm). These numbers are
our animation settings, not prescriptions quoted from the sources. The top target
accounts for lateral reach so the wider hands remain on the bar. Sources consulted
for technique only; no images, video, or mesh assets incorporated.

## Procedural training clothing (2026-10-24)

`core/clothes.py` constructs fitted shorts and a female sports top directly from
our existing CC0 MPFB body surface. It copies UV coordinates and rig weights,
interpolates both at garment cuts, and follows the corrected skin surface. No
external clothing mesh, image or texture has been downloaded. The geometry uses
the existing MPFB CC0 provenance; Z-Anatomy-derived highlights retain the licence
and attribution in `assets/maps/LICENSE.md`. Fabric disables anatomy bump relief.
