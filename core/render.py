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
        filt += "".join(f"[{r * m + c}:v]" for c in range(m)) + f"hstack=inputs={m}[r{r}];"
    filt += "".join(f"[r{r}]" for r in range(n)) + (f"vstack=inputs={n}[v]" if n > 1 else "copy[v]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args, "-filter_complex", filt,
                    "-map", "[v]", "-frames:v", "1", out_png], check=True)
    print("SHEET", out_png)
