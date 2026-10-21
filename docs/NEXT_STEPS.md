# Next steps after the approved animation baseline

The current 30 exercise versions are human-approved. They remain editable through
[the exercise workflow](EXERCISE_WORKFLOW.md); corrections create a new review cycle.

## 1. Preserve a versioned media release — completed 2026-10-21

Package `dist/` with its manifest, videos, posters, thumbnails and attribution files.
Include source commit and Blender/MPFB versions. Keep an immutable copy outside the
working render folder, and back up the local Blender profile/source maps. Source
and approval records are pushed to Git; generated media and local tooling are not.
Acceptance: the bundle passes the delivery audit and can be extracted independently.

## 2. Agree app architecture and scope before implementation

Architecture is proposed in [fitness-app](https://github.com/oktayshakirov/fitness-app).
Discuss mobile-first Expo versus a browser-first product, then collect the user’s
screenshots and feature requirements. No app implementation is authorized yet.
The following are candidate foundations, pending that discussion:
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

Approved media and tooling archives are stored at
`/Users/oktayshakirov/Coding/fitness-releases/v0.1.0/`; see
[the release receipt](releases/v0.1.0.json) for hashes and the source commit.
Media was extracted independently and every archived file checksum verified.
The tooling archive contains the local Blender profile, source maps and a verified
Git bundle. These are local snapshots, not offsite backups. Keep them out of Git.

Next: discuss the architecture proposal in fitness-app, then define features from
the user’s references before scaffolding. A separate fitness-blog is deferred.
