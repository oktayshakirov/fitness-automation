#!/usr/bin/env python3
"""Build one exercise: merge catalog/<id>.json (Agent B: muscles, text) with
motion/specs/<id>.json (Agent A: pattern, params, props, tempo, views), pose and key
every frame, attach the props, render, then write the review video + contact sheet.

    ./build.py <id> [--quick] [--views side,front] [--frames 1,20,40] [--keep-frames]
                    [--no-render] [--no-blend]

Plain python re-launches itself inside headless Blender with the project MPFB profile.
--quick renders only the contact-sheet frames (no video). Frame folders in review/ are
deleted after encoding unless --keep-frames."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"

try:
    import bpy
except ImportError:
    bpy = None

if bpy is None:
    import subprocess
    env = dict(os.environ, BLENDER_USER_RESOURCES=os.path.join(HERE, ".blender-profile"))
    cmd = [BLENDER, "-b", "--python-exit-code", "1", "--python", os.path.abspath(__file__), "--", *sys.argv[1:]]
    sys.exit(subprocess.run(cmd, env=env).returncode)

sys.path.insert(0, HERE)
import argparse, shutil, subprocess
from core import OUT
from core.body import make_human, key_pose
from core.solver import Poser
from core.look import muscle_material
from core.studio import studio, camera
from core.render import new_scene, render_views, stitch_video, contact_sheet, fit_delivery_cameras, export_delivery
from motion.tempo import Tempo
from motion import patterns, props as props_mod, micro

ap = argparse.ArgumentParser(prog="build.py")
ap.add_argument("id")
ap.add_argument("--delivery", action="store_true", help="QA-gated 720x900 app export; all views, one rep, both codecs")
ap.add_argument("--quick", action="store_true", help="render only the contact-sheet frames")
ap.add_argument("--views", help="comma-separated subset of the spec's views")
ap.add_argument("--frames", help="comma-separated frames for the sheet (and --quick)")
ap.add_argument("--keep-frames", action="store_true")
ap.add_argument("--no-render", action="store_true", help="pose + save the .blend only")
ap.add_argument("--no-blend", action="store_true")
ap.add_argument("--no-micro", action="store_true", help="no breathing / head settle / weight shift")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
if args.delivery and (args.no_render or args.quick or args.no_blend or args.views):
    ap.error("--delivery requires a full render, saved blend and every declared view")


def load_spec(eid):
    with open(os.path.join(HERE, "motion/specs", eid + ".json")) as fh:
        motion = json.load(fh)
    cat_path = os.path.join(HERE, "catalog", eid + ".json")
    catalog = {}
    if os.path.exists(cat_path):
        with open(cat_path) as fh:
            catalog = json.load(fh)
    else:
        print(f"WARNING: no catalog/{eid}.json, using draft_muscles from the motion spec")
        catalog = dict(motion.get("draft_muscles", {}))
    return motion, catalog


motion, catalog = load_spec(args.id)
tempo = Tempo(motion["tempo"])
N = tempo.n

scene = new_scene()
body, rig = make_human()
P = Poser(rig)
pattern = patterns.get(motion["pattern"])(P, motion.get("params", {}))
props = props_mod.build(P, motion.get("props", []))

micro_amp = float(motion.get("micro", 1.0)) if not args.no_micro else 0.0
for f in range(1, N + 1):
    micro.set_frame(P, f, N, micro_amp)
    P.reset()
    contacts = pattern.pose(tempo.s(f)) or {}
    key_pose(rig, f)
    for pr in props:
        pr.attach(f, contacts)
for pr in props:
    pr.finish(N)
micro.set_frame(P, 1, N, 0.0)
print("POSED", args.id, N, "frames")

body.data.materials.clear()
body.data.materials.append(muscle_material(primary=tuple(catalog.get("primary", ())),
                                           secondary=tuple(catalog.get("secondary", ()))))
delivery_objects=list(scene.objects)
studio(scene)
scene.frame_start, scene.frame_end = 1, N

cam_cfg = motion.get("camera", {})
target = cam_cfg.get("target", [0, 0, 1.0])
views = motion.get("views", [{"name": "front", "yaw": 0}, {"name": "side", "yaw": 90}])
views = [v if isinstance(v, dict) else {"name": v, "yaw": {"front": 0, "side": 90, "threeq": 35,
                                                           "back": 180}[v]} for v in views]
if args.views:
    keep = args.views.split(",")
    views = [v for v in views if v["name"] in keep]
cams = [camera(scene, v["name"], v.get("target", target), v["yaw"], ortho=v.get("ortho", cam_cfg.get("ortho", 2.2)),
               height=v.get("height", cam_cfg.get("height")))
        for v in views]

if args.delivery:
    fit_delivery_cameras(scene,cams,delivery_objects,[1,1+N//4,1+N//2,1+3*N//4,N])

sheet = [int(x) for x in args.frames.split(",")] if args.frames else motion.get("sheet") or tempo.key_frames()
if args.delivery:
    bpy.ops.wm.save_as_mainfile(filepath=OUT+f"{args.id}.blend")
    subprocess.run(["/usr/bin/env","python3",HERE+"/qa/check.py",args.id],check=True)
    from core.delivery import current_qa
    current_qa(args.id)

if not args.no_render:
    res = tuple(cam_cfg.get("res", (720, 1280)))      # review size; dist/ size is Agent B's
    if args.delivery: res=(720,900)
    dirs = render_views(scene, cams, args.id, 1, N, res=res, frames=sheet if args.quick else None)
    contact_sheet(dirs, sheet, OUT + f"{args.id}_sheet.png")
    if not args.quick:
        stitch_video(dirs, OUT + f"{args.id}.mp4",loops=1 if args.delivery else 3)
        if args.delivery: export_delivery(args.id,dirs,views)
    if not args.keep_frames:
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)
if not args.no_blend and not args.delivery:
    bpy.ops.wm.save_as_mainfile(filepath=OUT + f"{args.id}.blend")
print("BUILT", args.id)
