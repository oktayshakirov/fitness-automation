# MVP catalog

30 draft records. `reviewed: false` is deliberate: user/trainer review is still required.
Muscle arrays and difficulty are copied from free-exercise-db; they are its classification,
not a measured activation ranking. Equipment names are normalized to procedural asset IDs;
benches, racks and handles omitted by the source are added when required.
`adaptation` records variation changes (including the two-hand swing). Instructions, cues,
common mistakes and breathing text were newly written for these variations.

Source: https://github.com/yuhonas/free-exercise-db
Data: https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json
Licence checked 2026-10-16: Unlicense, saved in sources/LICENSE.free-exercise-db.
Downloaded data SHA-256: 5bb747e3fc658f095a60dcbf6d53c96627acdcc6ffb6fffde86f7e26995d40bf
Only the 30 selected source JSON records are retained; no external images/models added.

Run `python3 catalog/validate.py` to check IDs, schema, source muscle fidelity and the MVP count.
