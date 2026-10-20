# Next steps after the approved animation baseline

The current 30 exercise versions are human-approved. They remain editable through
[the exercise workflow](EXERCISE_WORKFLOW.md); corrections create a new review cycle.

## 1. Preserve a versioned media release

Package `dist/` with its manifest, videos, posters, thumbnails and attribution files.
Include source commit and Blender/MPFB versions. Keep an immutable copy outside the
working render folder, and back up the local Blender profile/source maps. Source
and approval records are pushed to Git; generated media and local tooling are not.
Acceptance: the bundle passes the delivery audit and can be extracted independently.

## 2. Build the Expo MVP around this bundle

Start with bundled/local media before choosing hosting or a backend:
- Front/back muscle selection plus an accessible muscle list.
- Exercise list filtered by primary/secondary muscle and equipment.
- Detail page with looping video, camera selector, steps, cues and breathing.
- Posters while loading; only the visible exercise plays; pause on backgrounding.
- Stable exercise IDs and manifest-driven paths so later releases replace assets
  without changing the app screens.

Acceptance: all 30 exercises work on an iPhone and Android device, filtering matches
catalog metadata, and playback/navigation stay smooth. Keep accounts, subscriptions,
workout tracking and cloud synchronization for a later scope decision.

## 3. Review in the app, then choose distribution

Use the same revise → preview → render → review flow for issues found on devices.
Choose static asset hosting/CDN and cache/update rules after measuring the local MVP.
Preserve prior release bundles so a new animation can be rolled back independently.

## 4. Add social-video exports and expand the catalog

Create a separate 9:16 composition with readable titles, muscle labels and safe
framing; render for that canvas instead of stretching the app's 4:5 clips. Then add
exercises by reusing validated movement/equipment patterns, in small review batches.

Recommended next work item: preserve the approved media release, then implement the
Expo muscle browser and exercise player. No app or publishing work has started here.
