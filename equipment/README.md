# Procedural gym library

All models are authored procedurally here; no external equipment assets. Metres, Z up,
body faces -Y. `barbell`, `ez_bar`, `kettlebell` root = grip centre; local X spans grip.
`rope`, `d_handle`, `v_bar`, `lat_bar`, `ankle_strap` root = cable ring. Grip offsets
are in each root's `contacts_json`. Rope endpoints animate via `update_rope`.
`pullup_bar(name,z)` root = bar centre (caller places root at z); other stations
have a ground origin. `exercise_mat()` avoids clashing with legacy `mat(material)`.

`bench` accepts incline -20..85°, seat_z, y0/y1. `contacts_json` exports pad plane,
length range and width. `Machine(kind)` exports `.contacts` and accepts
`.update(contacts,frame)`: pad/plate/handle contacts from motion patterns, or normalized
`travel` for Smith, hack squat, chest press and pec deck. These last four are equipment
prototypes; there are no approved corresponding exercise motions yet. Contact defaults
are for this MPFB body, not universal dimensions for every person.

`CableTower(pulley='high'|'mid'|'low', x=..., y_stack=..., y_front=...)` preserves
`calibrate(shortest_handle_ring)` then `update(ring,frame)`. `DualCable` owns two
independent stacks. The selector pin is 4 cm long: 1 cm recessed into the
17 cm-deep plates and a 3 cm exposed grip. The shared tower serves cable crossover,
face pull, rope pushdown and straight-bar pushdown. Seated cable row and lat
pulldown use the separate machine stack. `ResistanceBand.update(a,b,frame)` keys endpoints and thickness.

Run `equipment/preview.py` in Blender with the project profile to render all 30 assets
and regenerate `equipment/contacts.json`. Curves need evaluated mesh vertices for
camera bounds: Blender 5.2 curve bound_box can include a spurious 1 m radius.
