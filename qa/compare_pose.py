#!/usr/bin/env python3
"""Compare two pose dumps (qa/pose_dump.py): max bone/object translation and rotation
difference over all frames. Usage: compare_pose.py golden.json new.json [--map old=new]"""
import json, math, sys

a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
names = {}
for arg in sys.argv[3:]:
    if "=" in arg:
        k, v = arg.split("=")
        names[k] = v
worst_t, worst_r, where = 0.0, 0.0, None
missing = set()
for f in a:
    for kind in ("bones", "objects"):
        for n, m in a[f][kind].items():
            m2 = b[f][kind].get(names.get(n, n))
            if m2 is None:
                missing.add(n)
                continue
            dt = math.dist([r[3] for r in m[:3]], [r[3] for r in m2[:3]])
            dr = max(abs(m[i][j] - m2[i][j]) for i in range(3) for j in range(3))
            if dt > worst_t:
                worst_t, where = dt, (f, n)
            worst_r = max(worst_r, dr)
print(f"max translation diff {worst_t * 1000:.3f} mm at {where}; max rotation-matrix diff {worst_r:.5f}")
if missing:
    print("missing in new:", sorted(missing))
