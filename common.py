"""Compatibility shim: the shared helpers now live in core/. Old scripts keep
importing from here; new code imports from core.* directly."""
from core import ROOT, MAPS, OUT
from core.body import make_human, update, key_pose
from core.solver import frame, frame_align, two_bone, rot_x, rot_z, Poser
from core.look import GROUPS, mask_slot, load_masks, muscle_material, flat_material
from core.studio import studio, camera, BG
from core.render import new_scene, use_gpu, render_views, stitch_video, contact_sheet
