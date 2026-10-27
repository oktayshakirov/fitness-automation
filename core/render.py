"""Scene reset, render to frame folders, review video and contact sheet."""
import bpy, os, subprocess
from . import OUT


def new_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def use_gpu(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = "GPU"


def render_views(scene, cams, prefix, f0, f1, res=(720, 1280), frames=None):
    """Render frames f0..f1 for each camera into OUT/<prefix>_<cam>/####.png.
    frames (or the QUICK env var, comma-separated) renders only those frames."""
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    dirs = []
    for cam in cams:
        scene.camera = cam
        d = OUT + f"{prefix}_{cam.name}/"
        os.makedirs(d, exist_ok=True)
        # A new render never inherits stale frames from an earlier failed build.
        for old in os.listdir(d):
            if old.endswith(".png") and old[:-4].isdigit(): os.unlink(os.path.join(d,old))
        if frames is None and os.environ.get("QUICK"):
            frames = [int(x) for x in os.environ["QUICK"].split(",")]
        if frames:
            for f in frames:
                scene.frame_set(f)
                scene.render.filepath = d + f"{f:04d}.png"
                bpy.ops.render.render(write_still=True)
        else:
            scene.frame_start, scene.frame_end = f0, f1
            scene.render.filepath = d
            bpy.ops.render.render(animation=True)
        dirs.append(d)
        print("RENDERED", d)
    return dirs


def stitch_video(dirs, out_mp4, fps=30, loops=3):
    """Side-by-side mp4 of the per-camera frame folders, looped a few times."""
    inputs = []
    for d in dirs:
        inputs += ["-stream_loop", str(loops - 1), "-framerate", str(fps), "-i", d + "%04d.png"]
    filt = "".join(f"[{i}:v]" for i in range(len(dirs))) + f"hstack=inputs={len(dirs)},format=yuv420p[v]" \
        if len(dirs) > 1 else "[0:v]format=yuv420p[v]"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", filt,
                    "-map", "[v]", "-c:v", "libx264", "-crf", "20", out_mp4], check=True)
    print("VIDEO", out_mp4)


def contact_sheet(dirs, frames, out_png):
    """Grid: one row per camera, one column per frame."""
    if os.environ.get("QUICK"):
        frames = [int(x) for x in os.environ["QUICK"].split(",")]
    rows = []
    for d in dirs:
        rows.append("".join(f"-i {d}{f:04d}.png " for f in frames))
    args = []
    for d in dirs:
        for f in frames:
            args += ["-i", f"{d}{f:04d}.png"]
    n, m = len(dirs), len(frames)
    filt = ""
    for r in range(n):
        filt += "".join(f"[{r * m + c}:v]" for c in range(m)) + (f"hstack=inputs={m}[r{r}];" if m > 1 else f"copy[r{r}];")
    filt += "".join(f"[r{r}]" for r in range(n)) + (f"vstack=inputs={n}[v]" if n > 1 else "copy[v]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args, "-filter_complex", filt,
                    "-map", "[v]", "-frames:v", "1", out_png], check=True)
    print("SHEET", out_png)


def fit_delivery_cameras(scene,cams,objects,frames,margin=1.12):
    """Fit the full animated body/equipment in 4:5; ignore lights and studio floor.
    Evaluate curve vertices (Blender 5.2 curve bounding boxes are oversized).
    """
    from mathutils import Vector
    scene.render.resolution_x,scene.render.resolution_y=720,900
    scene.render.resolution_percentage=100
    for cam in cams:
        inv=cam.matrix_world.inverted()
        xs=[];ys=[]
        for f in frames:
            scene.frame_set(f);bpy.context.view_layer.update()
            inv=cam.matrix_world.inverted();dg=bpy.context.evaluated_depsgraph_get()
            for o in objects:
                if o.type not in ('MESH','CURVE') or o.hide_render:continue
                e=o.evaluated_get(dg);mesh=e.to_mesh();mx=inv@e.matrix_world
                coords=[mx@v.co for v in mesh.vertices]
                if coords:
                    xs.extend((min(v.x for v in coords),max(v.x for v in coords)))
                    ys.extend((min(v.y for v in coords),max(v.y for v in coords)))
                e.to_mesh_clear()
        xmin,xmax,ymin,ymax=min(xs),max(xs),min(ys),max(ys)
        offset=cam.matrix_world.to_3x3()@Vector(((xmin+xmax)/2,(ymin+ymax)/2,0))
        cam.location+=offset
        cam.data.ortho_scale=max(ymax-ymin,(xmax-xmin)/.8)*margin
    scene.frame_set(1)


def export_delivery(eid,dirs,views,qa_path=None,model=None):
    """Plain-Python encoder hook; invoke after full render and successful QA."""
    import json,tempfile
    from . import ROOT
    with tempfile.NamedTemporaryFile('w',suffix='.json',dir=OUT,delete=False) as f:
        json.dump({'dirs':dirs,'views':views,'model':model},f);path=f.name
    try:
        subprocess.run(['/usr/bin/env','python3',ROOT+'core/delivery.py',eid,path],check=True)
    finally:os.unlink(path)
